"""Candidate retrieval. STUB — owner: RAG. See team/04_RAG_AI.md Step 6."""
from app.mocks import sample_candidates, sample_explicit
from app.models import Behaviour, Candidate, Evidence


def retrieve_candidates(behaviours: list[Behaviour], k: int = 8) -> dict[str, list[Candidate]]:
    """STUB — owner: RAG. See team/04_RAG_AI.md.

    behaviour.id -> top-k candidates, best first.
    """
    return sample_candidates()


def explicit_ids(text: str) -> list[tuple[str, Evidence]]:
    """STUB — owner: RAG. See team/04_RAG_AI.md.

    Literal "T1234" / "T1234.001" mentions, with the sentence as evidence.
    """
    return sample_explicit()
