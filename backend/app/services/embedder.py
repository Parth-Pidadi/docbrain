"""
Embedder: chunks document text, generates BGE embeddings, stores in ChromaDB.

Every chunk is tagged with both doc_id and user_id so searches are always
scoped to the requesting user — no cross-user data leakage.

Embedding priority:
  1. Colab GPU  — fast batch embedding via colab_client
  2. Local CPU  — sentence-transformers fallback (lazy-loaded)
"""
from __future__ import annotations

from typing import Optional

import chromadb

from app.core.config import settings
from app.services import colab_client

_local_model = None
_collection = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("[embedder] Loading BGE model locally (no Colab)...")
            _local_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        except ImportError:
            print("[embedder] sentence-transformers not installed, Colab required for embeddings.")
            return None
    return _local_model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        _collection = client.get_or_create_collection(
            name="docbrain",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + chunk_size]))
        i += chunk_size - overlap
    return chunks


async def _get_embeddings(texts: list[str]) -> list[list[float]]:
    """Try Colab GPU first; fall back to local CPU."""
    colab_embeddings = await colab_client.embed_texts(texts)
    if colab_embeddings:
        return colab_embeddings

    model = _get_local_model()
    if model is None:
        raise RuntimeError("Colab GPU server is not available and sentence-transformers is not installed. Please start the Colab server.")
    return model.encode(texts, normalize_embeddings=True).tolist()


async def embed_and_store(doc_id: str, text: str, user_id: str = ""):
    """Chunk, embed, and upsert document into ChromaDB with user_id metadata."""
    collection = _get_collection()
    chunks = _chunk_text(text)
    if not chunks:
        return

    embeddings = await _get_embeddings(chunks)
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"doc_id": doc_id, "user_id": user_id, "chunk_index": i}
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )


async def search(
    query: str,
    doc_ids: Optional[list[str]] = None,
    user_id: str = "",
    top_k: int = 5,
) -> list[dict]:
    """
    Search ChromaDB for relevant chunks.
    Always filters by user_id to prevent cross-user data access.
    Optionally further restricts to specific doc_ids.
    """
    collection = _get_collection()
    query_embedding = (await _get_embeddings([query]))[0]

    # Always scope to the requesting user
    if doc_ids:
        where = {"$and": [{"user_id": {"$eq": user_id}}, {"doc_id": {"$in": doc_ids}}]}
    else:
        where = {"user_id": {"$eq": user_id}}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    return [
        {
            "doc_id": results["metadatas"][0][i]["doc_id"],
            "chunk": doc,
            "score": 1 - results["distances"][0][i],
        }
        for i, doc in enumerate(results["documents"][0])
    ]
