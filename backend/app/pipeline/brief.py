"""Plain-English briefing written ONLY from verified pipeline output. Owner: Lead.

The model sees accepted techniques with their quotes, kept IOCs with roles, CVE facts,
the attack-flow order and detection gaps, never the raw report. Code then drops any step
that cites a technique this analysis did not accept, and any action naming a CVE or
technique that is not in the verified data.
"""
import json
import re

from pydantic import BaseModel

from app.llm import UNTRUSTED_RULE, complete_json
from app.models import Briefing, BriefingAction, BriefingStep, ReportAnalysis

MAX_STEPS = 8
MAX_ACTIONS = 6
MAX_QUOTE_CHARS = 240
MAX_IOCS = 40
TECHNIQUE_ID = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
CVE_ID = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
IPV4 = re.compile(r"\b(?:\d{1,3}(?:\.|\[\.\])){3}\d{1,3}\b")
PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2}

SYSTEM_PROMPT = f"""You write a short briefing for a security team about one threat report.
You receive ONLY verified facts: ATT&CK techniques with the exact sentence from the report that proves each,
indicators with their roles, CVE facts from NVD and CISA KEV, the order of attack stages, and detection gaps.
Write in plain English for a busy IT manager. No jargon without explanation, no marketing words.
Rules:
- steps: the attack in order (follow the stage order given), at most {MAX_STEPS}. Each step says what the attacker did,
  using only the facts given. technique_ids must be IDs from the given list; tactic must be one of that technique's tactics.
- actions: at most {MAX_ACTIONS} concrete things to do now, most important first. kind is one of patch, block, logging, hunt.
  Only mention CVEs, indicators and techniques from the facts. Never invent versions, products or dates.
- If a fact is not given, do not state it.
{UNTRUSTED_RULE}"""


class _Step(BaseModel):
    title: str
    text: str
    technique_ids: list[str]
    tactic: str


class _Action(BaseModel):
    text: str
    priority: str
    kind: str
    technique_ids: list[str] = []
    cve_ids: list[str] = []


class _Out(BaseModel):
    steps: list[_Step] = []
    actions: list[_Action] = []


def _accepted(a: ReportAnalysis) -> dict:
    out = {}
    for t in a.techniques:
        if t.status == "accepted" and t.evidence and t.technique_id not in out:
            out[t.technique_id] = t
    return out


def _flow_order(a: ReportAnalysis) -> dict[str, int]:
    return {n.technique_id: n.order for n in a.flow.nodes if n.kind == "observed" and n.technique_id}


def _facts(a: ReportAnalysis, accepted: dict, order: dict[str, int]) -> str:
    techniques = sorted(accepted.values(), key=lambda t: (order.get(t.technique_id, 10**6), t.evidence.start))
    gaps = sorted({d.technique_id for d in a.detections if not d.strategies})
    return json.dumps({
        "techniques_in_attack_order": [
            {"id": t.technique_id, "name": t.name, "tactics": t.tactics,
             "proof": " ".join(t.evidence.quote.split())[:MAX_QUOTE_CHARS]} for t in techniques],
        "indicators": [{"value": i.display, "type": i.type, "role": i.role}
                       for i in a.iocs if not i.filtered_reason][:MAX_IOCS],
        "cves": [{"id": v.cve_id, "cvss": v.cvss_score, "severity": v.cvss_severity,
                  "in_cisa_kev": v.in_kev, "kev_required_action": v.kev_required_action,
                  "kev_due_date": v.kev_due_date, "known_ransomware_use": v.kev_ransomware_use,
                  "affected": v.affected} for v in a.vulnerabilities],
        "techniques_without_detection_guidance": gaps,
    }, indent=1)


def _source_for(kind: str, cve_ids: list[str], kev: set[str], technique_ids: list[str]) -> str | None:
    if kind == "patch" and cve_ids:
        return "cisa_kev" if any(c in kev for c in cve_ids) else "nvd_api"
    if technique_ids:
        return "attack_techniques"
    return None  # blocking indicators: the report itself is the source


def _kev_actions(a: ReportAnalysis) -> list[BriefingAction]:
    """Patching an actively exploited CVE comes first, and is written by code, not the model.

    Urgent when the CVE is central to this report: in its title, or inside the quote that proves an
    accepted technique. A KEV CVE the report only mentions in passing gets high priority.
    """
    proofs = " ".join(t.evidence.quote for t in a.techniques if t.status == "accepted" and t.evidence)
    actions = []
    for v in a.vulnerabilities:
        if not v.in_kev:
            continue
        central = v.cve_id in a.title.upper() or v.cve_id in proofs.upper()
        text = f"Patch {v.cve_id} — listed in CISA KEV (actively exploited)"
        if v.kev_due_date:
            text += f"; CISA due date: {v.kev_due_date}"
        if not central:
            text += ". Named in the report, but not part of the proven attack steps"
        actions.append(BriefingAction(text=text + ".", priority="urgent" if central else "high", kind="patch",
                                      cve_ids=[v.cve_id], source_key="cisa_kev"))
    actions.sort(key=lambda x: PRIORITY_ORDER[x.priority])
    return actions


def _defang_known(text: str, a: ReportAnalysis) -> str:
    """Indicators are shown defanged everywhere; the model sometimes writes them back live."""
    for ioc in sorted((i for i in a.iocs if i.type in ("ipv4", "ipv6", "domain", "url", "email")),
                      key=lambda i: len(i.value), reverse=True):
        text = text.replace(ioc.value, ioc.display)
    return re.sub(r"\bhttp(s?)://", r"hxxp\1://", text)


def _unknown_ips(text: str, a: ReportAnalysis) -> set[str]:
    kept = {i.value for i in a.iocs if i.type == "ipv4" and not i.filtered_reason}
    return {ip.replace("[.]", ".") for ip in IPV4.findall(text)} - kept


def check(raw: _Out, a: ReportAnalysis) -> Briefing:
    """The hard checks. Public so they can be exercised without an LLM."""
    accepted = _accepted(a)
    order = _flow_order(a)
    known_cves = {v.cve_id for v in a.vulnerabilities} | {i.value for i in a.iocs if i.type == "cve"}
    kev = {v.cve_id for v in a.vulnerabilities if v.in_kev}

    steps = []
    for s in raw.steps:
        ids = [t.strip().upper() for t in s.technique_ids]
        if not ids or any(t not in accepted for t in ids):
            continue  # cites a technique this analysis did not prove
        if any(t not in accepted for t in TECHNIQUE_ID.findall(f"{s.title} {s.text}")):
            continue
        tactics = {tac for t in ids for tac in accepted[t].tactics}
        tactic = s.tactic if s.tactic in tactics else accepted[ids[0]].tactics[0] if accepted[ids[0]].tactics else ""
        if _unknown_ips(s.text, a):
            continue
        steps.append(BriefingStep(title=s.title.strip(), text=_defang_known(s.text.strip(), a),
                                  technique_ids=ids, tactic=tactic))
    steps.sort(key=lambda s: min(order.get(t, 10**6) for t in s.technique_ids))

    kev_actions = _kev_actions(a)
    covered = {c for act in kev_actions for c in act.cve_ids}
    actions = []
    for act in raw.actions:
        if act.priority not in PRIORITY_ORDER or act.kind not in ("patch", "block", "logging", "hunt"):
            continue
        text_cves = {c.upper() for c in CVE_ID.findall(act.text)}
        cves = sorted({c.strip().upper() for c in act.cve_ids} | text_cves)
        tids = sorted({t.strip().upper() for t in act.technique_ids} | set(TECHNIQUE_ID.findall(act.text)))
        if any(c not in known_cves for c in cves) or any(t not in accepted for t in tids):
            continue  # names something that isn't in the verified data
        if _unknown_ips(act.text, a):
            continue  # an IP that isn't one of the report's kept indicators
        if act.kind == "patch" and cves and set(cves) <= covered:
            continue  # the code-written KEV action already says this
        actions.append(BriefingAction(text=_defang_known(act.text.strip(), a), priority=act.priority, kind=act.kind,
                                      technique_ids=tids, cve_ids=cves,
                                      source_key=_source_for(act.kind, cves, kev, tids)))
    actions.sort(key=lambda x: PRIORITY_ORDER[x.priority])
    urgent = [x for x in kev_actions if x.priority == "urgent"]
    rest = sorted([x for x in kev_actions if x.priority != "urgent"] + actions, key=lambda x: PRIORITY_ORDER[x.priority])
    return Briefing(steps=steps[:MAX_STEPS], actions=(urgent + rest)[:MAX_ACTIONS])


async def build_briefing(a: ReportAnalysis) -> Briefing | None:
    accepted = _accepted(a)
    if not accepted:
        return None  # nothing proven, nothing to brief
    raw = await complete_json(SYSTEM_PROMPT, _facts(a, accepted, _flow_order(a)), _Out,
                              model="verify", max_tokens=2500)
    return check(raw, a)
