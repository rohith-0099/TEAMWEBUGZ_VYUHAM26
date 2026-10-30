"""Local embeddings. STUB — owner: RAG. See team/04_RAG_AI.md Step 2."""


def get_model():
    """STUB — owner: RAG. See team/04_RAG_AI.md. Lazy fastembed singleton."""


def embed_passages(texts: list[str]) -> list[list[float]]:
    """STUB — owner: RAG. See team/04_RAG_AI.md. For techniques and examples."""
    return [[0.0] * 384 for _ in texts]


def embed_queries(texts: list[str]) -> list[list[float]]:
    """STUB — owner: RAG. See team/04_RAG_AI.md. For behaviours."""
    return [[0.0] * 384 for _ in texts]
