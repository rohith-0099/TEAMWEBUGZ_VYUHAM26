"""Quote finder. Owner: RAG. See team/04_RAG_AI.md Step 4."""

import re
from rapidfuzz import fuzz

from app.models import Evidence
from app.utils.text import normalize_text


def _normalize_curly_quotes(s: str) -> str:
    """Replace typographical quotes and dashes with ASCII equivalents."""
    return (
        s.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
    )


def _pick_nearest(matches: list[tuple[int, int]], near: int | None) -> tuple[int, int] | None:
    if not matches:
        return None
    if near is None:
        return matches[0]
    return min(matches, key=lambda m: abs(m[0] - near))


def find_quote(text: str, quote: str, near: int | None = None) -> tuple[Evidence, str] | None:
    """Locate an LLM-provided quote inside the canonical report text.

    Returns (Evidence with the REAL source substring + offsets, method) or None.
    method in {"exact", "normalized", "case", "whitespace", "ellipsis", "fuzzy"}.
    Always return Evidence(quote=text[start:end], start, end) — copied from source.
    """
    if not text or not quote:
        return None

    clean_q = quote.strip()
    if not clean_q:
        return None

    # 1. Exact match
    exact_matches: list[tuple[int, int]] = []
    idx = 0
    while True:
        pos = text.find(clean_q, idx)
        if pos == -1:
            break
        exact_matches.append((pos, pos + len(clean_q)))
        idx = pos + 1

    if exact_matches:
        start, end = _pick_nearest(exact_matches, near)
        return Evidence(quote=text[start:end], start=start, end=end), "exact"

    # 2. Normalized match (replace curly quotes, text normalization)
    norm_q = _normalize_curly_quotes(normalize_text(clean_q))
    norm_text = _normalize_curly_quotes(text)
    if norm_q != clean_q or norm_text != text:
        norm_matches: list[tuple[int, int]] = []
        idx = 0
        while True:
            pos = norm_text.find(norm_q, idx)
            if pos == -1:
                break
            norm_matches.append((pos, pos + len(norm_q)))
            idx = pos + 1
        if norm_matches:
            start, end = _pick_nearest(norm_matches, near)
            return Evidence(quote=text[start:end], start=start, end=end), "normalized"

    # 3. Case-insensitive match
    try:
        case_matches = [
            (m.start(), m.end())
            for m in re.finditer(re.escape(clean_q), text, flags=re.IGNORECASE)
        ]
        if case_matches:
            start, end = _pick_nearest(case_matches, near)
            return Evidence(quote=text[start:end], start=start, end=end), "case"
    except Exception:
        pass

    # 4. Whitespace-flexible match
    tokens = [t for t in re.split(r"\s+", clean_q) if t]
    if len(tokens) > 1:
        pattern = r"\s+".join(re.escape(t) for t in tokens)
        try:
            ws_matches = [
                (m.start(), m.end())
                for m in re.finditer(pattern, text, flags=re.IGNORECASE)
            ]
            if ws_matches:
                start, end = _pick_nearest(ws_matches, near)
                return Evidence(quote=text[start:end], start=start, end=end), "whitespace"
        except Exception:
            pass

    # 5. Ellipsis split match
    if "..." in clean_q or "…" in clean_q:
        parts = [p.strip() for p in re.split(r"\.\.\.|…", clean_q) if len(p.strip()) >= 12]
        if len(parts) >= 2:
            # Find first part
            p0 = parts[0]
            curr_pos = text.find(p0)
            if curr_pos == -1:
                # Try case insensitive
                m = re.search(re.escape(p0), text, flags=re.IGNORECASE)
                curr_pos = m.start() if m else -1

            if curr_pos != -1:
                span_start = curr_pos
                last_end = curr_pos + len(p0)
                matched_all = True

                for next_part in parts[1:]:
                    window_end = min(len(text), last_end + 400 + len(next_part))
                    window = text[last_end:window_end]
                    found = window.find(next_part)
                    if found == -1:
                        m = re.search(re.escape(next_part), window, flags=re.IGNORECASE)
                        found = m.start() if m else -1
                    if found == -1:
                        matched_all = False
                        break
                    last_end = last_end + found + len(next_part)

                if matched_all:
                    return Evidence(quote=text[span_start:last_end], start=span_start, end=last_end), "ellipsis"

    # 6. Fuzzy match via rapidfuzz (quote >= 25 chars)
    if len(clean_q) >= 25:
        if near is not None:
            win_start = max(0, near - 3000)
            win_end = min(len(text), near + 3000)
            search_text = text[win_start:win_end]
        else:
            win_start = 0
            search_text = text

        align = fuzz.partial_ratio_alignment(clean_q, search_text)
        if align and align.score >= 90:
            d_start = win_start + align.dest_start
            d_end = win_start + align.dest_end

            # Expand to word boundaries
            while d_start > 0 and text[d_start - 1].isalnum() and text[d_start].isalnum():
                d_start -= 1
            while d_end < len(text) and text[d_end - 1].isalnum() and text[d_end].isalnum():
                d_end += 1

            return Evidence(quote=text[d_start:d_end], start=d_start, end=d_end), "fuzzy"

    return None
