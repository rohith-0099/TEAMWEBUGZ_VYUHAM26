"""Behaviour agent. Owner: RAG. See team/04_RAG_AI.md Step 5."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
import re
from pydantic import BaseModel
from rapidfuzz import fuzz

from app.attack import store
from app.llm import complete_json, wrap_report, UNTRUSTED_RULE
from app.models import Behaviour, Evidence
from app.utils.sections import _heading_lines, in_reference_section, is_listing
from app.utils.quotes import find_quote

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are a senior cyber threat intelligence analyst. You extract ADVERSARY BEHAVIOURS from threat reports.
A behaviour is one concrete action that the attacker, their malware or their tools PERFORMED or were OBSERVED doing
(e.g. sending phishing attachments, executing PowerShell, dumping LSASS, adding a Run key, exfiltrating over HTTPS).
Rules:
- Copy the quote VERBATIM from the report: same words, same order, no paraphrase, no added words. 1-3 sentences.
- One behaviour per distinct action. Split sentences that describe several actions into several behaviours with the same quote.
- SKIP: defensive recommendations, mitigations, detection advice, generic background, vendor marketing,
  and descriptions of what defenders should do.
- NEVER use ATT&CK tables, appendices, technique lists or reference lists as quotes. A line that only gives a
  technique ID (T1234) or a technique name is not a behaviour. The quote must describe what the attacker did.
- Do not guess techniques or IDs. Do not invent behaviours not stated in the text.
- If nothing qualifies, return an empty list.
{UNTRUSTED_RULE}"""


MAX_BEHAVIOURS = 30


class _B(BaseModel):
    summary: str  # <= 20 words, present tense, e.g. "Malware adds a Run registry key to persist"
    quote: str  # VERBATIM from the report, 1-3 sentences, <= 400 chars
    actor_or_tool: str | None = None


class _Out(BaseModel):
    behaviours: list[_B] = []


def _split_into_chunks(text: str, max_chars: int = 6000) -> list[tuple[str, int]]:
    """Split text by paragraphs into chunks of <= max_chars with one paragraph of overlap.

    Returns list of (chunk_text, chunk_start_offset).
    """
    if not text:
        return []

    # Find paragraphs and their offsets
    matches = list(re.finditer(r"\n\s*\n", text))
    paras: list[tuple[str, int]] = []
    prev_idx = 0
    for m in matches:
        p_text = text[prev_idx:m.start()].strip()
        if p_text:
            paras.append((p_text, prev_idx))
        prev_idx = m.end()
    p_last = text[prev_idx:].strip()
    if p_last:
        paras.append((p_last, prev_idx))

    if not paras:
        return [(text[:max_chars], 0)]

    chunks: list[tuple[str, int]] = []
    curr_paras: list[tuple[str, int]] = []
    curr_len = 0

    for p_text, p_offset in paras:
        added_len = len(p_text) + 2
        if curr_paras and (curr_len + added_len > max_chars):
            # Emit current chunk
            chunk_start = curr_paras[0][1]
            chunk_text = "\n\n".join(p[0] for p in curr_paras)
            chunks.append((chunk_text, chunk_start))

            # Overlap: keep the last paragraph
            last_para = curr_paras[-1]
            curr_paras = [last_para, (p_text, p_offset)]
            curr_len = len(last_para[0]) + added_len
        else:
            curr_paras.append((p_text, p_offset))
            curr_len += added_len

    if curr_paras:
        chunk_start = curr_paras[0][1]
        chunk_text = "\n\n".join(p[0] for p in curr_paras)
        chunks.append((chunk_text, chunk_start))

    return chunks


def _spans_overlap_pct(s1: int, e1: int, s2: int, e2: int) -> float:
    overlap = max(0, min(e1, e2) - max(s1, s2))
    min_len = min(e1 - s1, e2 - s2)
    if min_len <= 0:
        return 0.0
    return overlap / min_len


async def extract_behaviours(
    text: str,
    on_behaviour: Callable[[Behaviour], Awaitable[None]] | None = None,
) -> list[Behaviour]:
    """Extract adversary behaviours with verbatim quotes, verified by find_quote."""
    if not text or not text.strip():
        return []

    chunks = _split_into_chunks(text)
    if not chunks:
        return []

    async def _process_chunk(chunk_text: str, chunk_start: int) -> list[tuple[_B, int]]:
        user_prompt = "Extract adversary behaviours from this part of a threat report.\n" + wrap_report(chunk_text)
        try:
            res: _Out = await complete_json(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                schema=_Out,
                model="extract",
                max_tokens=3000,
            )
            return [(b, chunk_start) for b in res.behaviours]
        except Exception as exc:
            logger.warning(f"Chunk extraction failed: {exc}")
            return []

    # Parallel LLM calls across chunks
    results = await asyncio.gather(*[_process_chunk(c_text, c_start) for c_text, c_start in chunks])
    raw_behaviours: list[tuple[_B, int]] = [item for sublist in results for item in sublist]

    # Verify quotes against full text
    candidates: list[tuple[str, Evidence]] = []
    for b_item, chunk_start in raw_behaviours:
        quote = (b_item.quote or "").strip()
        if not quote:
            continue
        found = find_quote(text, quote, near=chunk_start)
        if found is None:
            logger.debug(f"Dropped unverified quote from LLM: {quote[:60]}")
            continue
        evidence, _ = found
        summary = (b_item.summary or "").strip()
        candidates.append((summary, evidence))

    # Deduplicate: if two behaviours' spans overlap >= 70% and summaries token_set_ratio >= 80, keep one
    deduped: list[tuple[str, Evidence]] = []
    for summary, ev in candidates:
        is_dup = False
        for existing_summary, existing_ev in deduped:
            overlap = _spans_overlap_pct(ev.start, ev.end, existing_ev.start, existing_ev.end)
            if overlap >= 0.70:
                sim = fuzz.token_set_ratio(summary, existing_summary)
                if sim >= 80:
                    is_dup = True
                    break
        if not is_dup:
            deduped.append((summary, ev))

    # Lists of technique IDs/names are not evidence (CISA ATT&CK mapping best practices).
    headings = _heading_lines(text)
    names = store.technique_names()
    kept = []
    for summary, ev in deduped:
        if is_listing(ev.quote, names) or in_reference_section(text, ev.start, headings):
            logger.debug(f"Dropped listing/appendix quote: {ev.quote[:60]}")
            continue
        kept.append((summary, ev))

    # Sort by evidence.start, cap: the verifier makes one call per BATCH of behaviours
    kept.sort(key=lambda item: item[1].start)
    deduped = kept[:MAX_BEHAVIOURS]

    final_behaviours: list[Behaviour] = []
    for idx, (summary, ev) in enumerate(deduped, start=1):
        b = Behaviour(
            id=f"b-{idx}",
            summary=summary,
            evidence=ev,
        )
        final_behaviours.append(b)
        if on_behaviour:
            try:
                await on_behaviour(b)
            except Exception as e:
                logger.warning(f"on_behaviour callback error: {e}")

    return final_behaviours
