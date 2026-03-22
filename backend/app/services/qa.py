"""
RAG Q&A: retrieves relevant chunks from ChromaDB, answers with Groq LLM.
Search is always scoped to the requesting user via user_id.
"""
from __future__ import annotations

from typing import Optional

import groq

from app.core.config import settings
from app.models.schemas import QAResponse, QASource
from app.services import embedder

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = groq.Groq(api_key=settings.GROQ_API_KEY)
    return _client


QA_SYSTEM = """You are DocBrain, an AI assistant that answers questions about uploaded documents.
Answer ONLY based on the provided context. If the answer is not in the context, say "I couldn't find that in the uploaded documents."
Always cite which document your answer comes from."""

QA_PROMPT = """Context from documents:
{context}

Question: {question}

Answer:"""


async def answer(
    question: str,
    doc_ids: Optional[list[str]] = None,
    user_id: str = "",
) -> QAResponse:
    # Retrieve relevant chunks — always scoped to this user
    chunks = await embedder.search(question, doc_ids=doc_ids, user_id=user_id, top_k=5)

    if not chunks:
        return QAResponse(
            answer="No documents have been processed yet. Please upload and extract a document first.",
            sources=[],
            model=settings.GROQ_MODEL,
        )

    context = "\n\n---\n\n".join(
        f"[Doc {c['doc_id'][:8]}...] {c['chunk']}" for c in chunks
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": QA_SYSTEM},
            {"role": "user", "content": QA_PROMPT.format(context=context, question=question)},
        ],
        max_tokens=512,
        temperature=0.1,
    )

    answer_text = response.choices[0].message.content.strip()

    sources = [
        QASource(
            doc_id=c["doc_id"],
            filename=c["doc_id"],  # filename resolved via DB in route layer
            chunk=c["chunk"],
            score=c["score"],
        )
        for c in chunks
    ]

    return QAResponse(answer=answer_text, sources=sources, model=settings.GROQ_MODEL)
