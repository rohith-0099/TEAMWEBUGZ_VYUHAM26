"""Local embeddings. Owner: RAG. See team/04_RAG_AI.md Step 2."""
from typing import Any
import numpy as np

from app.config import settings

_model: Any = None
USE_QUERY_PREFIX: bool = True
QUERY_PREFIX: str = "Represent this sentence for searching relevant passages: "


def get_model():
    """Lazy fastembed singleton, settings.embed_model."""
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name=settings.embed_model)
        except Exception:
            return None
    return _model


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1e-12
    return vectors / norms


def embed_passages(texts: list[str]) -> list[list[float]]:
    """For techniques and examples. Normalized to unit length."""
    if not texts:
        return []
    model = get_model()
    if model is None:
        return [[0.0] * 384 for _ in texts]

    embeddings = list(model.embed(texts, batch_size=128))
    arr = np.array(embeddings, dtype=np.float32)
    normed = _normalize(arr)
    return normed.tolist()


def embed_queries(texts: list[str]) -> list[list[float]]:
    """For behaviours. Normalized to unit length."""
    if not texts:
        return []
    if USE_QUERY_PREFIX:
        prefixed = [f"{QUERY_PREFIX}{t}" for t in texts]
    else:
        prefixed = texts

    model = get_model()
    if model is None:
        return [[0.0] * 384 for _ in texts]

    if hasattr(model, "query_embed") and not USE_QUERY_PREFIX:
        embeddings = list(model.query_embed(texts, batch_size=128))
    else:
        embeddings = list(model.embed(prefixed, batch_size=128))
    arr = np.array(embeddings, dtype=np.float32)
    normed = _normalize(arr)
    return normed.tolist()
