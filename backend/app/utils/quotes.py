"""Quote finder. STUB — owner: RAG. See team/04_RAG_AI.md Step 4."""
from app.models import Evidence


def find_quote(text: str, quote: str, near: int | None = None) -> tuple[Evidence, str] | None:
    """STUB — owner: RAG. See team/04_RAG_AI.md.

    Locates an LLM quote in the canonical text; the stub only tries an exact match.
    Returns (Evidence, method), method in {"exact","normalized","case","whitespace","ellipsis","fuzzy"}.
    """
    start = text.find(quote)
    if start < 0:
        return None
    return Evidence(quote=quote, start=start, end=start + len(quote)), "exact"
