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
from app.llm import UNTRUSTED_RULE, LLMError, complete_json, wrap_report
from app.mocks import sample_analysis
from app.models import IOC, Behaviour, Candidate, Confidence, Evidence, TechniqueMatch
from app.utils.quotes import find_quote

log = logging.getLogger(__name__)

CONTEXT_CHARS = 300
EXPLICIT_NEAR_CHARS = 500
DESCRIPTION_CHARS = 450
EXAMPLES_PER_CANDIDATE = 1
MAX_CANDIDATES_SENT = 6  # retrieval ranks them; explicit IDs always go in
MAX_VERIFY_TOKENS = 1500
MAX_REJECTED_PER_BEHAVIOUR = 3
OUTSIDE_CANDIDATES_FACTOR = 0.8
FUZZY_QUOTE_FACTOR = 0.9

SYSTEM_PROMPT = f"""You verify mappings between threat-report evidence and MITRE ATT&CK v20 techniques.
You receive one adversary behaviour, its exact evidence from the report, surrounding context, and candidate techniques
with their OFFICIAL MITRE descriptions. Decide which candidates (0, 1 or 2) the evidence actually supports.
Rules:
- Judge ONLY against the official description. Similar words are not enough; the described action must match.
- Choose a sub-technique only if the evidence supports that specific variant; otherwise choose the parent technique.
- If no candidate fits, return no matches. Returning nothing is better than a wrong match.
- evidence_quote must be copied VERBATIM from the evidence or context (shortest span that proves the match).
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


class _Out(BaseModel):
    matches: list[_Match]
    rejected: list[_Rej] = []


def _attack_url(row: dict | None) -> str | None:
    return row.get("url") if row else None


def _rejected(technique_id: str, reason: str, rationale: str, evidence: Evidence | None,
              behaviour_id: str | None, name: str = "", mapping: float | None = None) -> TechniqueMatch:
    row = store.get_technique(technique_id)
    return TechniqueMatch(
        technique_id=technique_id, name=(row or {}).get("name") or name or "Unknown technique",
        tactics=(row or {}).get("tactics") or [], behaviour_id=behaviour_id, evidence=evidence,
        status="rejected", reject_reason=reason, rationale=rationale,
        confidence=Confidence(mapping=mapping), url=_attack_url(row),
    )


def _judge(match: _Match, text: str, behaviour: Behaviour, behaviour_id: str | None,
           candidate_ids: set[str], ioc_ids: set[str]) -> TechniqueMatch:
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
    lines += [f"Example: {e}" for e in examples]
    return "\n".join(lines)


def _user_prompt(text: str, behaviour: Behaviour, blocks: list[str], iocs: list[IOC]) -> str:
    start = max(0, behaviour.evidence.start - CONTEXT_CHARS)
    end = behaviour.evidence.end + CONTEXT_CHARS
    nearby = [i for i in iocs if not i.filtered_reason
              and any(start <= e.start < end for e in i.evidence)]
    indicators = "\n".join(f"{i.id}: {i.display} ({i.type})" for i in nearby) or "none"
    return (f"Behaviour: {behaviour.summary}\n\n"
            f"Evidence and context:\n{wrap_report(behaviour.evidence.quote)}\n"
            f"{wrap_report(text[start:end])}\n\n"
            f"Indicators in context:\n{indicators}\n\n"
            "Candidates:\n" + "\n\n".join(blocks))


async def _verify_behaviour(text: str, behaviour: Behaviour, behaviour_id: str | None,
                            candidates: list[Candidate], iocs: list[IOC],
                            emit: Callable[[TechniqueMatch], Awaitable[None]]) -> None:
    ordered = sorted(candidates, key=lambda c: c.score, reverse=True)[:MAX_CANDIDATES_SENT]
    blocks = [b for b in map(_candidate_block, ordered) if b]
    if not blocks:
        return
    out = await complete_json(SYSTEM_PROMPT, _user_prompt(text, behaviour, blocks, iocs), _Out,
                              model="verify", max_tokens=MAX_VERIFY_TOKENS)

    candidate_ids = {c.technique_id for c in ordered}
    ioc_ids = {i.id for i in iocs}
    judged = [_judge(m, text, behaviour, behaviour_id, candidate_ids, ioc_ids) for m in out.matches]
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
    if not settings.llm_api_key:
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

    tasks = []
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
        tasks.append(_verify_behaviour(text, b, b.id, pool, iocs, emit))

    for tid, evidence in usable.items():
        if tid not in placed:  # no nearby behaviour: its sentence is the evidence
            name = (store.get_technique(tid) or {}).get("name", tid)
            sentence = Behaviour(id=f"explicit-{tid}", summary=f"The report names {tid}", evidence=evidence)
            pool = [Candidate(technique_id=tid, name=name, score=1.0, source="explicit_id")]
            tasks.append(_verify_behaviour(text, sentence, None, pool, iocs, emit))

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [o for o in outcomes if isinstance(o, BaseException)]
    for failure in failures:
        if not isinstance(failure, LLMError):
            raise failure  # a bug, not a flaky model: don't hide it
        log.warning("verifier skipped a behaviour: %s", failure)
    if tasks and len(failures) == len(tasks):
        raise LLMError(f"All {len(tasks)} verifier calls failed; last error: {failures[-1]}")
    return results
