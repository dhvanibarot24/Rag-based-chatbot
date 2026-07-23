"""
embedding.py

Loads the SentenceTransformers embedding model once and reuses it for
every request. Embeddings are only generated during document upload;
queries reuse this same model to embed the user's question at search time
(a single short embedding call, not a recomputation of stored vectors).
"""

from typing import List

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None  # lazy-loaded singleton


def get_model() -> SentenceTransformer:
    """Load the embedding model once and cache it for the process lifetime."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of document chunks (used once, during upload)."""
    if not texts:
        return []
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(text: str) -> List[float]:
    """Embed a single user question at query time."""
    model = get_model()
    embedding = model.encode([text], convert_to_numpy=True, show_progress_bar=False)
    return embedding[0].tolist()