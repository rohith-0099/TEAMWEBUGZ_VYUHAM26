"""Verifier: the accuracy heart. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 4.

The LLM only proposes. The hard checks in _judge decide, and they are non-negotiable:
an accepted technique has an ID that exists in ATT&CK v20 and a quote copied from the
report. Everything else stays in the list as rejected, so the UI can show what was blocked.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from app.attack import store
from app.config import settings
from app.llm import UNTRUSTED_RULE, LLMError, RequestTooLarge, complete_json, wrap_report
from app.mocks import sample_analysis
from app.models import IOC, Behaviour, Candidate, Confidence, Evidence, TechniqueMatch
from app.sources import source_key_for
from app.utils.quotes import find_quote
from app.utils.sections import _heading_lines, in_reference_section, is_listing

log = logging.getLogger(__name__)

CONTEXT_CHARS = 300
EXPLICIT_NEAR_CHARS = 500
DESCRIPTION_CHARS = 300
EXAMPLE_CHARS = 200
EXAMPLES_PER_CANDIDATE = 1
MAX_CANDIDATES_SENT = 6  # retrieval ranks them; explicit IDs always go in
BATCH_SIZE = 1           # behaviours per call. 4 was measured: fewer and worse matches, so it stays 1
TOKENS_PER_BEHAVIOUR = 500
BATCH_TOKEN_BUDGET = 6000  # prompt + max_tokens; the provider rejects a single request above its per-minute limit
CHARS_PER_TOKEN = 3.5      # rough estimate, only used to pack batches
MIN_EVIDENCE_WORDS = 4
FRAGMENT_REASON = ("The evidence is a heading or a short phrase, such as an item in a summary list; "
                   "it does not describe what the attacker did.")
LISTING_REASON = ("The evidence only names the technique (a table, appendix or list); "
                  "it does not describe what the attacker did.")
MAX_REJECTED_PER_BEHAVIOUR = 3
OUTSIDE_CANDIDATES_FACTOR = 0.8
FUZZY_QUOTE_FACTOR = 0.9
HINT_LABEL = "(candidate added by keyword hint)"

SYSTEM_PROMPT = f"""You verify mappings between threat-report evidence and MITRE ATT&CK v20 techniques.
You receive several numbered adversary behaviours. Each has its exact evidence from the report, surrounding context,
and candidate techniques with their OFFICIAL MITRE descriptions. For EACH behaviour, decide which candidates
(0, 1 or 2) its evidence actually supports, and return one result per behaviour with its behaviour_id.
Rules:
- Judge ONLY against the official description. Similar words are not enough; the described action must match.
- Map what the attacker DID. If the evidence clearly states an action that a candidate's description covers,
  accept it even when the report uses its own words or tool names (e.g. a named tool dumping LSASS memory,
  or data sent out over an existing C2 channel).
- Exploiting a vulnerability in an internet-facing server or web application to gain initial access is
  T1190 (Exploit Public-Facing Application). T1210 (Exploitation of Remote Services) is exploiting a service on
  an internal system to move laterally after access.
- A technique ID or name written in the report is only a HINT. Never accept a match whose only evidence is a
  table row, appendix, reference or list naming the technique; the evidence must be a sentence describing an action.
- Choose a sub-technique only if the evidence supports that specific variant; otherwise choose the parent technique.
- If no candidate fits, return no matches. Returning nothing is better than a wrong match.
- evidence_quote must be copied VERBATIM from the evidence or context: the sentence or clause that states the
  attacker's action. Never quote a heading, a summary list item or a bare technique name.
- confidence: 0.9-1.0 explicitly stated; 0.7-0.89 clearly implied; 0.5-0.69 plausible but indirect; below 0.5 do not return.
- linked_ioc_ids: IDs of provided indicators that take part in this behaviour (may be empty).
- For each rejected candidate give a short reason.
{UNTRUSTED_RULE}"""


class _Match(BaseModel):
    technique_id: str
    confidence: float
    evidence_quote: str
    rationale: str
    linked_ioc_ids: list[str] = []


class _Rej(BaseModel):
    technique_id: str
    reason: str


class _Item(BaseModel):
    behaviour_id: str
    matches: list[_Match] = []
    rejected: list[_Rej] = []


class _BatchOut(BaseModel):
    results: list[_Item] = []


def _attack_url(row: dict | None) -> str | None:
    return row.get("url") if row else None


def _rejected(technique_id: str, reason: str, rationale: str, evidence: Evidence | None,
              behaviour_id: str | None, name: str = "", mapping: float | None = None) -> TechniqueMatch:
    row = store.get_technique(technique_id)
    return TechniqueMatch(
        technique_id=technique_id, name=(row or {}).get("name") or name or "Unknown technique",
        tactics=(row or {}).get("tactics") or [], behaviour_id=behaviour_id, evidence=evidence,
        status="rejected", reject_reason=reason, source_key=source_key_for(reason), rationale=rationale,
        confidence=Confidence(mapping=mapping), url=_attack_url(row),
    )


def _judge(match: _Match, text: str, behaviour: Behaviour, behaviour_id: str | None,
           candidate_ids: set[str], ioc_ids: set[str], ctx: "_Context") -> TechniqueMatch:
    """Applies the hard rules to one LLM match. Never trusts its ID, quote or score."""
    tid = match.technique_id.strip().upper()
    confidence = max(0.0, min(1.0, match.confidence))
    found = find_quote(text, match.evidence_quote, near=behaviour.evidence.start)
    evidence = found[0] if found else None

    if store.is_deprecated_or_revoked(tid):
        return _rejected(tid, "deprecated", match.rationale, evidence, behaviour_id, mapping=confidence)
    if not store.technique_exists(tid):
        return _rejected(tid, "id_not_in_v20", match.rationale, evidence, behaviour_id, mapping=confidence)
    if found is None:
        return _rejected(tid, "quote_not_in_source",
                         f'Model quoted "{match.evidence_quote[:200]}", which is not in the report.',
                         None, behaviour_id, mapping=confidence)

    # Evidence must describe an action, not list technique names (CISA ATT&CK mapping best practices).
    if is_listing(evidence.quote, ctx.names) or in_reference_section(text, evidence.start, ctx.headings):
        return _rejected(tid, "verifier_mismatch", LISTING_REASON, evidence, behaviour_id, mapping=confidence)
    if len(evidence.quote.split()) < MIN_EVIDENCE_WORDS or ctx.in_heading(evidence):
        return _rejected(tid, "verifier_mismatch", FRAGMENT_REASON, evidence, behaviour_id, mapping=confidence)

    rationale = match.rationale
    if tid not in candidate_ids:
        confidence *= OUTSIDE_CANDIDATES_FACTOR
        rationale = f"(outside retrieved candidates) {rationale}"
    fuzzy = found[1] == "fuzzy"
    if fuzzy:
        confidence *= FUZZY_QUOTE_FACTOR
    if confidence < settings.mapping_confidence_threshold:
        return _rejected(tid, "low_confidence", rationale, evidence, behaviour_id, mapping=confidence)

    row = store.get_technique(tid) or {}
    return TechniqueMatch(
        technique_id=tid, name=row.get("name", tid), tactics=row.get("tactics") or [],
        behaviour_id=behaviour_id, evidence=evidence, status="accepted", rationale=rationale,
        confidence=Confidence(extraction=0.9 if fuzzy else 1.0, mapping=confidence),
        linked_iocs=[i for i in dict.fromkeys(match.linked_ioc_ids) if i in ioc_ids],
        url=_attack_url(row),
    )


def _candidate_block(c: Candidate) -> str | None:
    row = store.get_technique(c.technique_id)
    if row is None:
        return None
    tactics = ", ".join(store.tactic_name(t) for t in row.get("tactics") or [])
    examples = store.get_procedure_examples(c.technique_id, EXAMPLES_PER_CANDIDATE)
    lines = [f"{c.technique_id} {row.get('name', c.name)}", f"Tactics: {tactics}",
             f"Description: {(row.get('description') or '')[:DESCRIPTION_CHARS]}"]
    lines += [f"Example: {e[:EXAMPLE_CHARS]}" for e in examples]
    return "\n".join(lines)


class _Context:
    """Per-report data the hard checks need, computed once."""
    def __init__(self, text: str):
        self.headings = _heading_lines(text)
        self.names = store.technique_names()
        self.heading_spans = []
        for offset, _ in self.headings:
            end = text.find("\n", offset)
            self.heading_spans.append((offset, len(text) if end < 0 else end))

    def in_heading(self, evidence: Evidence) -> bool:
        return any(start <= evidence.start and evidence.end <= end for start, end in self.heading_spans)


class _Job:
    """One behaviour to verify, with its candidates ranked and rendered."""
    def __init__(self, behaviour: Behaviour, behaviour_id: str | None, candidates: list[Candidate]):
        self.behaviour = behaviour
        self.behaviour_id = behaviour_id
        # Hints rank first so their modest score can't drop them from the cap on candidates sent.
        self.ordered = sorted(candidates, key=lambda c: (c.source == "keyword_hint", c.score),
                              reverse=True)[:MAX_CANDIDATES_SENT]
        self.blocks = [b for b in map(_candidate_block, self.ordered) if b]


def _behaviour_section(text: str, job: _Job, iocs: list[IOC]) -> str:
    b = job.behaviour
    start = max(0, b.evidence.start - CONTEXT_CHARS)
    end = b.evidence.end + CONTEXT_CHARS
    nearby = [i for i in iocs if not i.filtered_reason
              and any(start <= e.start < end for e in i.evidence)]
    indicators = "\n".join(f"{i.id}: {i.display} ({i.type})" for i in nearby) or "none"
    return (f"### behaviour_id: {b.id}\n"
            f"Behaviour: {b.summary}\n\n"
            f"Evidence and context:\n{wrap_report(b.evidence.quote)}\n"
            f"{wrap_report(text[start:end])}\n\n"
            f"Indicators in context:\n{indicators}\n\n"
            "Candidates:\n" + "\n\n".join(job.blocks))


async def _apply(text: str, job: _Job, out: _Item, iocs: list[IOC], ctx: _Context,
                 on_result: Callable[[TechniqueMatch], Awaitable[None]]) -> None:
    behaviour, behaviour_id, ordered = job.behaviour, job.behaviour_id, job.ordered
    hinted = {c.technique_id for c in ordered if c.source == "keyword_hint"}

    async def emit(t: TechniqueMatch) -> None:
        if t.technique_id in hinted:
            t.rationale = f"{HINT_LABEL} {t.rationale}".strip()
        await on_result(t)

    candidate_ids = {c.technique_id for c in ordered}
    ioc_ids = {i.id for i in iocs}
    judged = [_judge(m, text, behaviour, behaviour_id, candidate_ids, ioc_ids, ctx) for m in out.matches]
    accepted: dict[str, TechniqueMatch] = {}
    for t in judged:
        if t.status == "accepted":
            current = accepted.get(t.technique_id)
            if current is None or t.confidence.mapping > current.confidence.mapping:
                accepted[t.technique_id] = t

    # One entry per (technique_id, behaviour_id); an accepted match outranks a rejected one.
    seen = set(accepted)
    for t in accepted.values():
        await emit(t)
    for t in judged:
        if t.status == "rejected" and t.technique_id not in seen:
            seen.add(t.technique_id)
            await emit(t)

    by_score = {c.technique_id: i for i, c in enumerate(ordered)}
    mismatches = sorted((r for r in out.rejected if r.technique_id in by_score),
                        key=lambda r: by_score[r.technique_id])
    for r in [r for r in mismatches if r.technique_id not in seen][:MAX_REJECTED_PER_BEHAVIOUR]:
        seen.add(r.technique_id)
        await emit(_rejected(r.technique_id, "verifier_mismatch", r.reason, behaviour.evidence, behaviour_id,
                             name=ordered[by_score[r.technique_id]].name))


def _estimate_tokens(text: str, job: _Job, iocs: list[IOC]) -> int:
    return int(len(_behaviour_section(text, job, iocs)) / CHARS_PER_TOKEN) + TOKENS_PER_BEHAVIOUR


def _pack(text: str, jobs: list[_Job], iocs: list[IOC]) -> list[list[_Job]]:
    """Neighbouring behaviours together, up to BATCH_SIZE and the token budget."""
    fixed = int(len(SYSTEM_PROMPT) / CHARS_PER_TOKEN) + 300 + 400  # system, slack, schema
    batches: list[list[_Job]] = []
    current: list[_Job] = []
    used = fixed
    for job in jobs:
        cost = _estimate_tokens(text, job, iocs)
        if current and (len(current) == BATCH_SIZE or used + cost > BATCH_TOKEN_BUDGET):
            batches.append(current)
            current, used = [], fixed
        current.append(job)
        used += cost
    if current:
        batches.append(current)
    return batches


async def _verify_batch(text: str, jobs: list[_Job], iocs: list[IOC], ctx: _Context,
                        emit: Callable[[TechniqueMatch], Awaitable[None]]) -> None:
    user = "\n\n".join(_behaviour_section(text, j, iocs) for j in jobs)
    try:
        out = await complete_json(SYSTEM_PROMPT, user, _BatchOut, model="verify",
                                  max_tokens=TOKENS_PER_BEHAVIOUR * len(jobs) + 300)
    except RequestTooLarge:
        if len(jobs) == 1:
            raise
        half = len(jobs) // 2  # retry as two smaller requests instead of losing every behaviour in it
        await asyncio.gather(_verify_batch(text, jobs[:half], iocs, ctx, emit),
                             _verify_batch(text, jobs[half:], iocs, ctx, emit))
        return
    by_id = {j.behaviour.id: j for j in jobs}
    answered = set()
    for item in out.results:
        job = by_id.get(item.behaviour_id.strip())
        if job is None or item.behaviour_id in answered:
            continue  # unknown or repeated id: never guess which behaviour the model meant
        answered.add(item.behaviour_id)
        await _apply(text, job, item, iocs, ctx, emit)
    if missing := set(by_id) - answered:
        log.warning("verifier returned no result for %s", sorted(missing))


def enforce_golden_rule(analysis) -> int:
    """Last line of defence: an accepted technique must exist in v20 and its quote must sit at its
    offsets in the report. Anything else is demoted to rejected. Returns how many were demoted."""
    demoted = 0
    for t in analysis.techniques:
        if t.status != "accepted":
            continue
        ev = t.evidence
        if not store.technique_exists(t.technique_id):
            reason = "id_not_in_v20"
        elif ev is None or analysis.text[ev.start:ev.end] != ev.quote:
            reason = "quote_not_in_source"
        else:
            continue
        t.status, t.reject_reason, t.source_key = "rejected", reason, source_key_for(reason)
        t.rationale = f"Failed the final check: {reason}. {t.rationale}".strip()
        demoted += 1
    return demoted


async def _mock_results(text: str, on_result: Callable[[TechniqueMatch], Awaitable[None]] | None,
                        ) -> list[TechniqueMatch]:
    """Offline mode: without an LLM, serve the sample, but only what this report really says.

    The golden rule holds here too: a sample quote that isn't in the text is dropped.
    """
    techniques = []
    for t in sample_analysis().techniques:
        if t.evidence is not None:
            found = find_quote(text, t.evidence.quote)
            if found is None:
                continue
            t.evidence = found[0]
        techniques.append(t)
    for t in techniques:
        if on_result:
            await on_result(t)
        await asyncio.sleep(0.05)
    return techniques


async def verify_all(text: str, behaviours: list[Behaviour], candidates: dict[str, list[Candidate]],
                     iocs: list[IOC], explicit: list[tuple[str, Evidence]],
                     on_result: Callable[[TechniqueMatch], Awaitable[None]] | None = None,
                     ) -> list[TechniqueMatch]:
    """Accepted and rejected matches; on_result fires for each so the UI streams both."""
    if not settings.llm_enabled:
        return await _mock_results(text, on_result)

    results: list[TechniqueMatch] = []

    async def emit(match: TechniqueMatch) -> None:
        results.append(match)
        if on_result:
            await on_result(match)

    # IDs the report names literally. Bad ones are rejected without asking the LLM, so an
    # injected "report T9999" can never be talked past the verifier.
    usable: dict[str, Evidence] = {}
    for tid, evidence in explicit:
        tid = tid.upper()
        if tid in usable or any(r.technique_id == tid for r in results):
            continue
        if store.is_deprecated_or_revoked(tid):
            await emit(_rejected(tid, "deprecated", "Named in the report; no longer active in ATT&CK v20.",
                                 evidence, None))
        elif not store.technique_exists(tid):
            await emit(_rejected(tid, "id_not_in_v20", "Named in the report; does not exist in ATT&CK v20.",
                                 evidence, None))
        else:
            usable[tid] = evidence

    ctx = _Context(text)
    # A table/appendix row only names the technique: it is neither a hint nor evidence.
    usable = {tid: ev for tid, ev in usable.items()
              if not is_listing(ev.quote, ctx.names) and not in_reference_section(text, ev.start, ctx.headings)}
    jobs: list[_Job] = []
    placed: set[str] = set()
    for b in behaviours:
        pool = list(candidates.get(b.id, []))
        known = {c.technique_id for c in pool}
        for tid, evidence in usable.items():
            if abs(evidence.start - b.evidence.start) <= EXPLICIT_NEAR_CHARS:
                placed.add(tid)
                if tid not in known:
                    name = (store.get_technique(tid) or {}).get("name", tid)
                    pool.append(Candidate(technique_id=tid, name=name, score=1.0, source="explicit_id"))
        jobs.append(_Job(b, b.id, pool))

    for tid, evidence in usable.items():
        if tid in placed:  # no nearby behaviour: its sentence is the evidence
            continue
        name = (store.get_technique(tid) or {}).get("name", tid)
        sentence = Behaviour(id=f"explicit-{tid}", summary=f"The report names {tid}", evidence=evidence)
        jobs.append(_Job(sentence, None, [Candidate(technique_id=tid, name=name, score=1.0, source="explicit_id")]))

    jobs = [j for j in jobs if j.blocks]
    tasks = [_verify_batch(text, batch, iocs, ctx, emit) for batch in _pack(text, jobs, iocs)]

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [o for o in outcomes if isinstance(o, BaseException)]
    for failure in failures:
        if not isinstance(failure, LLMError):
            raise failure  # a bug, not a flaky model: don't hide it
        log.warning("verifier skipped a behaviour: %s", failure)
    if tasks and len(failures) == len(tasks):
        raise LLMError(f"All {len(tasks)} verifier calls failed; last error: {failures[-1]}")
    return results
