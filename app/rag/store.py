from typing import Optional
from uuid import uuid4

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from app.config import get_settings
from app.rag.embedder import embed_single, embed_texts
from app.rag.chunker import Chunk

settings = get_settings()

SCORE_CONFIDENT = 0.78
SCORE_PARTIAL = 0.50
SCORE_MIN = 0.30  # below this, don't even return


async def store_chunks(
    chunks: list[Chunk],
    company_id: str,
    doc_id: str,
    metadata: dict,
    client: AsyncQdrantClient,
) -> int:
    """Embed and upsert all chunks into Qdrant. Returns count stored."""
    if not chunks:
        return 0

    texts = [c.text for c in chunks]
    vectors = await embed_texts(texts)

    points = []
    for chunk, vector in zip(chunks, vectors):
        payload = {
            "text": chunk.text,
            "company_id": company_id,
            "doc_id": doc_id,
            "chunk_index": chunk.chunk_index,
            "chunk_type": chunk.chunk_type,
            "section_title": chunk.section_title,
            **metadata,
        }
        points.append(PointStruct(id=str(uuid4()), vector=vector, payload=payload))

    await client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
    return len(points)


async def _rerank_with_jina(query: str, chunks: list[dict], top_n: int) -> list[dict]:
    """Re-rank chunks using Jina reranker. Falls back to original order on any error."""
    if not settings.JINA_API_KEY or not chunks:
        return chunks[:top_n]
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.post(
                "https://api.jina.ai/v1/rerank",
                headers={
                    "Authorization": f"Bearer {settings.JINA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.JINA_RERANKER_MODEL,
                    "query": query,
                    "documents": [c["text"] for c in chunks],
                    "top_n": min(top_n, len(chunks)),
                },
            )
        if res.status_code != 200:
            return chunks[:top_n]
        reranked = []
        for r in res.json().get("results", []):
            c = dict(chunks[r["index"]])
            c["score"] = round(r["relevance_score"], 3)
            reranked.append(c)
        return reranked
    except Exception:
        return chunks[:top_n]


async def query_with_confidence(
    query: str,
    company_id: str,
    property_id: Optional[str] = None,
    top_k: int = 5,
    client: Optional[AsyncQdrantClient] = None,
) -> dict:
    """
    Query Qdrant and return chunks with a confidence assessment.
    Fetches top_k * 3 candidates, Jina re-ranks to top_k, then scores confidence.

    Returns:
      {
        "confidence": "CONFIDENT" | "PARTIAL" | "NO_MATCH",
        "chunks": [{"text": ..., "score": ..., "metadata": ...}],
        "max_score": float,
        "context_text": str,   # formatted for LLM injection
      }
    """
    if client is None:
        from app.dependencies import _qdrant_client
        client = _qdrant_client

    query_vector = await embed_single(query)

    conditions = [FieldCondition(key="company_id", match=MatchValue(value=company_id))]
    if property_id:
        conditions.append(FieldCondition(key="property_id", match=MatchValue(value=property_id)))

    # Fetch 3× candidates so Jina has a wider pool to re-rank
    fetch_k = top_k * 3
    results = await client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vector,
        query_filter=Filter(must=conditions),
        limit=fetch_k,
        score_threshold=SCORE_MIN,
        with_payload=True,
    )

    if not results:
        return {"confidence": "NO_MATCH", "chunks": [], "max_score": 0.0, "context_text": ""}

    candidates = [
        {
            "text": r.payload.get("text", ""),
            "score": round(r.score, 3),
            "metadata": {k: v for k, v in r.payload.items() if k != "text"},
        }
        for r in results
    ]

    # Jina re-rank — narrows candidates to top_k, best match first
    chunks = await _rerank_with_jina(query, candidates, top_n=top_k)

    max_score = max(c["score"] for c in chunks) if chunks else 0.0

    if max_score >= SCORE_CONFIDENT:
        confidence = "CONFIDENT"
    elif max_score >= SCORE_PARTIAL:
        confidence = "PARTIAL"
    else:
        confidence = "NO_MATCH"

    context_text = _format_context(chunks)

    return {
        "confidence": confidence,
        "chunks": chunks,
        "max_score": round(max_score, 3),
        "context_text": context_text,
    }


async def delete_doc_chunks(doc_id: str, client: AsyncQdrantClient) -> None:
    """Remove all Qdrant points for a given doc_id."""
    await client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )


def _format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a string for system prompt injection."""
    parts = []
    for i, c in enumerate(chunks, 1):
        score_pct = int(c["score"] * 100)
        title = c["metadata"].get("section_title", "")
        header = f"[Source {i} — {score_pct}% match{f' | {title}' if title else ''}]"
        parts.append(f"{header}\n{c['text']}")
    return "\n\n---\n\n".join(parts)
