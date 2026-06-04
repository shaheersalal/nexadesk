import asyncio
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.middleware import CurrentUser, CompanyId
from app.config import get_settings
from app.dependencies import get_supabase_admin
from app.rag.pipeline import ingest_file, ingest_text
from app.rag.store import query_with_confidence

router = APIRouter()
settings = get_settings()

# In-memory job status tracker (fine for demo; use Redis for production)
_job_status: dict[str, dict] = {}


# ── Ingest file upload ────────────────────────────────────────────────────────

@router.post("/ingest")
async def ingest_document(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    company_id: CompanyId,
    file: UploadFile = File(...),
    category: str = Form(default="other"),
    property_id: Optional[str] = Form(default=None),
):
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    job_id = str(uuid4())
    _job_status[job_id] = {"status": "processing", "filename": file.filename}

    background_tasks.add_task(
        _run_ingest_file,
        job_id, file_bytes, file.filename, company_id, category, current_user["id"], property_id
    )

    return {"job_id": job_id, "filename": file.filename, "status": "processing"}


async def _run_ingest_file(job_id, file_bytes, filename, company_id, category, user_id, property_id):
    try:
        result = await ingest_file(
            file_bytes=file_bytes,
            filename=filename,
            company_id=company_id,
            category=category,
            uploaded_by=user_id,
            property_id=property_id,
        )
        _job_status[job_id] = {"status": "completed", "filename": filename, **result}
    except Exception as e:
        _job_status[job_id] = {"status": "failed", "filename": filename, "error": str(e)}


# ── Ingest plain text ─────────────────────────────────────────────────────────

class TextIngestRequest(BaseModel):
    text: str
    category: str = "notes"
    property_id: Optional[str] = None
    title: Optional[str] = None


@router.post("/ingest/text")
async def ingest_text_endpoint(
    body: TextIngestRequest,
    current_user: CurrentUser,
    company_id: CompanyId,
):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    result = await ingest_text(
        text=body.text,
        company_id=company_id,
        metadata={
            "source_type": "text_paste",
            "property_id": body.property_id or "",
            "doc_category": body.category,
            "filename": body.title or "pasted_text",
        },
    )
    return result


# ── Job status ────────────────────────────────────────────────────────────────

@router.get("/status/{job_id}")
async def get_job_status(job_id: str, current_user: CurrentUser):
    status = _job_status.get(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


# ── Query (for internal use by chat/voice engines) ────────────────────────────

class QueryRequest(BaseModel):
    query: str
    property_id: Optional[str] = None
    top_k: int = 5


@router.post("/query")
async def query_rag(
    body: QueryRequest,
    current_user: CurrentUser,
    company_id: CompanyId,
):
    result = await query_with_confidence(
        query=body.query,
        company_id=company_id,
        property_id=body.property_id,
        top_k=body.top_k,
    )
    return result


# ── List documents ────────────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents(company_id: CompanyId, current_user: CurrentUser):
    sb = get_supabase_admin()
    result = (
        sb.table("documents")
        .select("*")
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, company_id: CompanyId, current_user: CurrentUser):
    from app.rag.store import delete_doc_chunks
    from app.dependencies import _qdrant_client
    sb = get_supabase_admin()
    sb.table("documents").delete().eq("id", doc_id).eq("company_id", company_id).execute()
    if _qdrant_client:
        await delete_doc_chunks(doc_id, _qdrant_client)
