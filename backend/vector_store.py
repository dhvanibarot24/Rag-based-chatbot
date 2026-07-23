"""
vector_store.py

Thin wrapper around a persistent ChromaDB collection used to store and
retrieve document chunk embeddings.

The collection is created once with get_or_create_collection() and is
never dropped or recreated on startup, so uploaded documents survive
server restarts.

Every stored chunk carries this metadata so retrieval can always be
filtered to the requesting user's own documents:
    user_id, document_id, original_filename, chunk_id
"""

import os
from typing import Dict, List, Optional

import chromadb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", os.path.join(BASE_DIR, "chroma_db"))
COLLECTION_NAME = "user_documents"

# A single persistent client/collection reused for the lifetime of the process.
_client = chromadb.PersistentClient(path=CHROMA_PATH)
_collection = _client.get_or_create_collection(name=COLLECTION_NAME)


def add_document_chunks(
    user_id: int,
    document_id: int,
    original_filename: str,
    chunks: List[str],
    embeddings: List[List[float]],
) -> None:
    """Store one document's chunk embeddings with their metadata."""
    if not chunks:
        return

    ids = [f"{document_id}_{index}" for index in range(len(chunks))]
    metadatas = [
        {
            "user_id": str(user_id),
            "document_id": str(document_id),
            "original_filename": original_filename,
            "chunk_id": index,
        }
        for index in range(len(chunks))
    ]

    _collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )


def query_user_chunks(
    user_id: int,
    query_embedding: List[float],
    top_k: int = 5,
) -> List[Dict[str, object]]:
    """Retrieve the most relevant chunks belonging only to this user.

    Returns a list of {"text": ..., "filename": ...} dicts, best match first.
    """
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"user_id": str(user_id)},
    )

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]

    chunks = []
    for text, metadata in zip(documents[0], metadatas[0]):
        chunks.append(
            {
                "text": text,
                "filename": metadata.get("original_filename", "document"),
            }
        )
    return chunks


def user_has_documents(user_id: int) -> bool:
    """Cheap check used to give a clearer message when a user has nothing uploaded."""
    existing = _collection.get(where={"user_id": str(user_id)}, limit=1)
    return bool(existing.get("ids"))


def delete_document_chunks(document_id: int) -> None:
    """Remove every chunk belonging to a deleted document. No orphan embeddings."""
    _collection.delete(where={"document_id": str(document_id)})