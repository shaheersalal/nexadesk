"""
High-level ingestion pipeline. Called by the router (for file uploads)
and by properties/router.py (for auto-ingestion of property forms).
"""
from uuid import uuid4
from typing import Optional

from app.rag.detector import detect_file_type, assess_quality, InputMeta
from app.rag.extractor import extract_text
from app.rag.cleaner import clean
from app.rag.chunker import smart_chunk
from app.rag.store import store_chunks
from app.dependencies import get_supabase_admin


async def ingest_file(
    file_bytes: bytes,
    filename: str,
    company_id: str,
    category: str,
    uploaded_by: str,
    property_id: Optional[str] = None,
    doc_id: Optional[str] = None,
) -> dict:
    """
    Full ingestion pipeline for a file upload.
    Creates/updates a documents record in Supabase, runs extraction/cleaning/embedding.
    Returns {"doc_id": ..., "chunk_count": ..., "quality_score": ...}
    """
    from app.dependencies import _qdrant_client

    doc_id = doc_id or str(uuid4())
    sb = get_supabase_admin()

    # 1. Upload raw file to Supabase Storage (best-effort — don't fail ingest if storage is unavailable)
    storage_path = None
    try:
        from app.config import get_settings as _gs
        bucket = _gs().SUPABASE_STORAGE_BUCKET
        storage_path = f"{company_id}/{doc_id}/{filename}"
        sb.storage.from_(bucket).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/octet-stream", "upsert": "true"},
        )
    except Exception:
        storage_path = None  # Storage not configured or failed — continue with ingest

    # 2. Track document in Supabase (status=processing)
    sb.table("documents").upsert({
        "id": doc_id,
        "company_id": company_id,
        "filename": filename,
        "category": category,
        "property_id": property_id,
        "status": "processing",
        "uploaded_by": uploaded_by,
        **({"storage_path": storage_path} if storage_path else {}),
    }).execute()

    try:
        # 3. Detect file type
        meta = detect_file_type(file_bytes, filename)

        # 4. Extract text
        raw_text = await extract_text(file_bytes, meta, filename)

        # 5. Assess quality
        quality = assess_quality(raw_text)

        # 6. Clean
        clean_text = await clean(raw_text, quality)

        # 7. Chunk
        chunks = smart_chunk(clean_text)

        # 8. Embed + store in Qdrant
        chunk_count = await store_chunks(
            chunks=chunks,
            company_id=company_id,
            doc_id=doc_id,
            metadata={
                "filename": filename,
                "file_type": meta.file_type,
                "doc_category": category,
                "property_id": property_id or "",
                "quality_score": round(quality.score, 2),
                "llm_cleaned": quality.needs_llm_clean,
            },
            client=_qdrant_client,
        )

        # 9. Update Supabase record
        sb.table("documents").update({
            "status": "completed",
            "chunk_count": chunk_count,
            "quality_score": round(quality.score, 2),
            "file_type": meta.file_type,
        }).eq("id", doc_id).eq("company_id", company_id).execute()

        return {
            "doc_id": doc_id,
            "chunk_count": chunk_count,
            "quality_score": round(quality.score, 2),
            "flags": quality.flags,
        }

    except Exception as e:
        sb.table("documents").update({
            "status": "failed",
            "error_message": str(e)[:500],
        }).eq("id", doc_id).eq("company_id", company_id).execute()
        raise


async def ingest_text(
    text: str,
    company_id: str,
    metadata: dict,
    doc_id: Optional[str] = None,
) -> dict:
    """
    Ingest plain text (from dashboard textarea or auto-generated property summaries).
    Skips file detection and extraction steps.
    """
    from app.dependencies import _qdrant_client

    doc_id = doc_id or str(uuid4())

    quality = assess_quality(text)
    clean_text = await clean(text, quality)
    chunks = smart_chunk(clean_text)

    chunk_count = await store_chunks(
        chunks=chunks,
        company_id=company_id,
        doc_id=doc_id,
        metadata={
            "quality_score": round(quality.score, 2),
            "llm_cleaned": quality.needs_llm_clean,
            **metadata,
        },
        client=_qdrant_client,
    )

    return {
        "doc_id": doc_id,
        "chunk_count": chunk_count,
        "quality_score": round(quality.score, 2),
    }
