"""
embedding.py

Loads the SentenceTransformers embedding model once and reuses it for
every request. Embeddings are only generated during document upload;
queries reuse this same model to embed the user's question at search time
(a single short embedding call, not a recomputation of stored vectors).

MEMORY OPTIMIZATION:
`sentence_transformers` pulls in `torch` and `transformers`, which together
can add several hundred MB of RAM the moment they're imported -- even before
any model weights are loaded. On a 512 MB Render instance that cost is paid
at process startup if imported at module level, which:
  1. Slows down / can crash the app's cold start, and
  2. Wastes RAM for requests that never touch RAG (e.g. login, signup).

So the import itself is deferred into get_model(), and only runs the first
time someone actually uploads a document or asks a question. The model
instance is still cached (the `_model` singleton) so it is loaded at most
once per running process, never re-loaded per request.
"""

from typing import Any, List

MODEL_NAME = "all-MiniLM-L6-v2"

_model: Any = None  # lazy-loaded singleton, populated on first real use


def get_model() -> Any:
    """Load the embedding model once and cache it for the process lifetime.

    Heavy imports live inside this function on purpose -- see module docstring.
    """
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        # A single CPU thread keeps memory and CPU contention low on a
        # constrained instance; the model is small enough that this has
        # negligible impact on latency for one request at a time.
        torch.set_num_threads(1)

        _model = SentenceTransformer(MODEL_NAME, device="cpu")

    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of document chunks (used once, during upload)."""
    if not texts:
        return []
    model = get_model()
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=16,  # keeps peak memory flat regardless of document size
    )
    result = embeddings.tolist()
    del embeddings  # release the numpy array promptly
    return result


def embed_query(text: str) -> List[float]:
    """Embed a single user question at query time."""
    model = get_model()
    embedding = model.encode([text], convert_to_numpy=True, show_progress_bar=False)
    result = embedding[0].tolist()
    del embedding
    return result