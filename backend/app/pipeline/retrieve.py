"""Candidate retrieval. Owner: RAG. See team/04_RAG_AI.md Step 6."""

import re
from typing import Any
import numpy as np
from rapidfuzz import fuzz

from app.attack.embed import embed_queries
from app.attack.store import (
    _PROCEDURE_EXAMPLES,
    _TECHNIQUES,
    _ensure_initialized,
    get_technique,
)
from app.db import pool
from app.models import Behaviour, Candidate, Evidence

# In-memory vector index
_INDEX_INITIALIZED: bool = False
_TECH_IDS: list[str] = []
_TECH_NAMES: list[str] = []
_TECH_PARENTS: list[str | None] = []
_TECH_MATRIX: np.ndarray | None = None  # (N_tech, 384)
_EX_TECH_IDS: list[str] = []
_EX_MATRIX: np.ndarray | None = None    # (N_ex, 384)

STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "was", "were", "is", "are", "using", "used", "into", "over",
}


def _init_index() -> None:
    global _INDEX_INITIALIZED, _TECH_IDS, _TECH_NAMES, _TECH_PARENTS, _TECH_MATRIX, _EX_TECH_IDS, _EX_MATRIX
    if _INDEX_INITIALIZED:
        return

    _ensure_initialized()

    # Try loading from Postgres
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT technique_id, name, parent_id, embedding
                    FROM attack_techniques
                    WHERE embedding IS NOT NULL
                    """
                )
                t_rows = cur.fetchall()
                if t_rows:
                    _TECH_IDS = [r["technique_id"] if isinstance(r, dict) else r[0] for r in t_rows]
                    _TECH_NAMES = [r["name"] if isinstance(r, dict) else r[1] for r in t_rows]
                    _TECH_PARENTS = [r["parent_id"] if isinstance(r, dict) else r[2] for r in t_rows]
                    embs = [r["embedding"] if isinstance(r, dict) else r[3] for r in t_rows]
                    _TECH_MATRIX = np.array(embs, dtype=np.float32)

                cur.execute("SELECT technique_id, embedding FROM attack_examples WHERE embedding IS NOT NULL")
                ex_rows = cur.fetchall()
                if ex_rows:
                    _EX_TECH_IDS = [r["technique_id"] if isinstance(r, dict) else r[0] for r in ex_rows]
                    ex_embs = [r["embedding"] if isinstance(r, dict) else r[1] for r in ex_rows]
                    _EX_MATRIX = np.array(ex_embs, dtype=np.float32)
    except Exception:
        pass

    # If DB has no vectors, populate technique metadata from store
    if not _TECH_IDS:
        for tid, t_data in _TECHNIQUES.items():
            _TECH_IDS.append(tid)
            _TECH_NAMES.append(t_data.get("name", ""))
            _TECH_PARENTS.append(t_data.get("parent_id"))

    _INDEX_INITIALIZED = True


def explicit_ids(text: str) -> list[tuple[str, Evidence]]:
    """Literal 'T1234' / 'T1234.001' mentions in the report, with the sentence as evidence."""
    if not text:
        return []

    pattern = re.compile(r"\b(T\d{4}(?:\.\d{3})?)\b")
    results: list[tuple[str, Evidence]] = []

    delimiters = [". ", ".\n", "\n", "? ", "! "]

    for m in pattern.finditer(text):
        tid = m.group(1)
        m_start = m.start()
        m_end = m.end()

        # Find preceding boundary
        s_start = 0
        for delim in delimiters:
            idx = text.rfind(delim, 0, m_start)
            if idx != -1:
                s_start = max(s_start, idx + len(delim))

        # Find following boundary
        s_end = len(text)
        for delim in delimiters:
            idx = text.find(delim, m_end)
            if idx != -1:
                s_end = min(s_end, idx + (1 if delim.startswith(".") else len(delim)))

        sentence = text[s_start:s_end].strip()
        actual_start = text.find(sentence, s_start)
        actual_end = actual_start + len(sentence)
        ev = Evidence(quote=text[actual_start:actual_end], start=actual_start, end=actual_end)
        results.append((tid, ev))

    return results


SYNONYMS: dict[str, list[str]] = {
    "https": ["web protocols", "http", "ssl", "tls", "application layer protocol"],
    "http": ["web protocols", "https", "application layer protocol"],
    "beacon": ["c2", "command and control", "web protocols", "application layer protocol"],
    "base64": ["deobfuscate", "decode", "obfuscation", "deobfuscate/decode", "files or information"],
    "decoded": ["deobfuscate", "decode", "deobfuscate/decode", "files or information"],
    "decode": ["deobfuscate", "deobfuscate/decode", "files or information"],
    "sam": ["security account manager", "credential dumping", "registry hive", "os credential dumping"],
    "dictionary": ["brute force", "password guessing"],
    "brute": ["brute force", "password guessing"],
    "screenshot": ["screen capture"],
    "screenshots": ["screen capture"],
    "hosts": ["stored data manipulation", "impair defenses", "modify tools"],
    "ssh": ["protocol tunneling", "proxy", "internal proxy", "remote services"],
    "ftp": ["exfiltration over alternative protocol", "non-application layer protocol", "unencrypted"],
    "wmi": ["windows management instrumentation"],
    "wmic": ["windows management instrumentation"],
    "antivirus": ["security software discovery"],
    "7-zip": ["archive collected data", "archive via utility", "compression"],
    "compressed": ["archive collected data", "archive via utility"],
    "staged": ["data staged", "local data staging"],
}


def _expand_query(q_text: str) -> str:
    words = re.findall(r"\w+", q_text.lower())
    extra: list[str] = []
    for w in words:
        if w in SYNONYMS:
            extra.extend(SYNONYMS[w])
    return f"{q_text} {' '.join(extra)}" if extra else q_text


def _score_lexical(q_text: str, tid: str, t_data: dict[str, Any]) -> float:
    expanded = _expand_query(q_text)
    q_lower = expanded.lower()
    name = t_data.get("name", "").lower()
    parent_id = t_data.get("parent_id")
    parent_name = _TECHNIQUES.get(parent_id, {}).get("name", "").lower() if parent_id else ""
    full_name = f"{parent_name}: {name}" if parent_name else name

    # 1. Full name match (max of WRatio and token_set_ratio)
    name_score = max(fuzz.WRatio(full_name, q_lower), fuzz.token_set_ratio(full_name, q_lower))

    # 2. Description token set ratio
    desc = t_data.get("description", "")[:600].lower()
    desc_score = fuzz.token_set_ratio(q_lower, desc)

    # 3. Procedure examples
    examples = _PROCEDURE_EXAMPLES.get(tid, [])
    best_ex_score = 0.0
    for ex in examples[:15]:
        s = fuzz.token_set_ratio(q_lower, ex.lower())
        if s > best_ex_score:
            best_ex_score = float(s)

    combined = (name_score * 0.50) + (desc_score * 0.20) + (best_ex_score * 0.30)
    return combined / 100.0


# Exploiting a CVE/vulnerability, or an exploit request against a web server, php-cgi or an
# internet-facing system, is the ATT&CK T1190 pattern. Retrieval sometimes ranks T1210 instead, so T1190
# is added as a hint; the verifier still decides against the official descriptions.
_PUBLIC_FACING_EXPLOIT = re.compile(
    r"(exploit\w*|weaponi[sz]\w*)[^.]{0,120}(CVE-\d{4}-\d+|vulnerab\w*|flaw|web ?server|web application|"
    r"php-cgi|public-facing|internet-facing|exposed)"
    r"|(CVE-\d{4}-\d+|vulnerab\w*|flaw|php-cgi)[^.]{0,120}exploit\w*"
    r"|exploit request", re.IGNORECASE)
T1190 = "T1190"


def _add_public_facing_hint(behaviour: Behaviour, candidates: list[Candidate]) -> list[Candidate]:
    text = f"{behaviour.summary} {behaviour.evidence.quote}"
    if not _PUBLIC_FACING_EXPLOIT.search(text) or any(c.technique_id == T1190 for c in candidates):
        return candidates
    row = get_technique(T1190)
    if row is None:
        return candidates
    # Placed first so it survives the verifier's cap on candidates sent.
    return [Candidate(technique_id=T1190, name=row["name"], score=1.0, source="explicit_id"), *candidates]


def retrieve_candidates(behaviours: list[Behaviour], k: int = 6) -> dict[str, list[Candidate]]:
    """behaviour.id -> top-k candidates, best first (plus the T1190 hint where it applies)."""
    if not behaviours:
        return {}
    return {bid: _add_public_facing_hint(next(b for b in behaviours if b.id == bid), cands)
            for bid, cands in _retrieve(behaviours, k).items()}


def _retrieve(behaviours: list[Behaviour], k: int) -> dict[str, list[Candidate]]:

    _init_index()

    # Build query texts
    query_texts = [f"{b.summary}. {b.evidence.quote}" for b in behaviours]
    q_embs = embed_queries(query_texts)
    q_matrix = np.array(q_embs, dtype=np.float32)

    has_valid_embs = (
        _TECH_MATRIX is not None
        and _TECH_MATRIX.size > 0
        and np.linalg.norm(q_matrix) > 1e-4
        and np.linalg.norm(_TECH_MATRIX) > 1e-4
    )

    results: dict[str, list[Candidate]] = {}

    if has_valid_embs:
        # Vector dot products: shape (B, N_tech)
        sim_tech = np.clip(q_matrix @ _TECH_MATRIX.T, -1.0, 1.0)

        # Examples dot products: shape (B, N_ex)
        sim_ex = None
        if _EX_MATRIX is not None and _EX_MATRIX.size > 0:
            sim_ex = np.clip(q_matrix @ _EX_MATRIX.T, -1.0, 1.0)

        for b_idx, b in enumerate(behaviours):
            scores: dict[str, float] = {}

            for t_idx, tid in enumerate(_TECH_IDS):
                scores[tid] = float(sim_tech[b_idx, t_idx])

            if sim_ex is not None:
                for e_idx, tid in enumerate(_EX_TECH_IDS):
                    ex_score = float(sim_ex[b_idx, e_idx]) * 0.98
                    if tid in scores:
                        scores[tid] = max(scores[tid], ex_score)
                    else:
                        scores[tid] = ex_score

            for tid, parent_id in zip(_TECH_IDS, _TECH_PARENTS):
                if parent_id and parent_id != tid and tid in scores:
                    parent_score = scores[tid] * 0.95
                    if parent_id in scores:
                        scores[parent_id] = max(scores[parent_id], parent_score)
                    else:
                        scores[parent_id] = parent_score

            sorted_tids = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)[:k]
            candidates = []
            for tid in sorted_tids:
                t_info = get_technique(tid)
                name = t_info["name"] if t_info else tid
                candidates.append(
                    Candidate(
                        technique_id=tid,
                        name=name,
                        score=round(max(0.0, min(1.0, scores[tid])), 4),
                        source="vector",
                    )
                )
            results[b.id] = candidates
    else:
        # Rich hybrid lexical retriever when fastembed vectors are not yet loaded
        for b in behaviours:
            q_text = f"{b.summary}. {b.evidence.quote}"
            scores: dict[str, float] = {}
            for tid, t_data in _TECHNIQUES.items():
                scores[tid] = _score_lexical(q_text, tid, t_data)

            for tid, t_data in _TECHNIQUES.items():
                parent_id = t_data.get("parent_id")
                if parent_id and parent_id in scores:
                    scores[parent_id] = max(scores[parent_id], scores[tid] * 0.95)

            sorted_tids = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)[:k]
            candidates = [
                Candidate(
                    technique_id=tid,
                    name=_TECHNIQUES[tid].get("name", tid),
                    score=round(min(1.0, max(0.0, scores[tid])), 4),
                    source="vector",
                )
                for tid in sorted_tids
            ]
            results[b.id] = candidates

    return results
