from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.middleware import CurrentUser, CompanyId, AccessibleCompanyIds
from app.config import get_settings
from app.dependencies import get_supabase_admin
from app.rag.pipeline import ingest_file, ingest_text
from app.rag.store import query_with_confidence
from app.shared.llm import complete
from app.shared import session_store

router = APIRouter()
settings = get_settings()

PURIFY_SYSTEM = """You are processing a voice transcript from a real estate agency owner. They spoke naturally about properties, prices, services, or business info.

Convert the raw speech into clean, structured knowledge base content:
- Remove filler words (um, uh, you know, like, so, basically, actually, right)
- Convert spoken numbers: "one point five million" → "1,500,000", "three fifty" → "350,000"
- Organize into clear paragraphs or bullet points
- Preserve ALL factual details: prices, addresses, sizes, bedrooms, features, contacts, policies
- Write a short descriptive title on the very first line (e.g. "Villa Listings — Arabian Ranches")

Output only the cleaned content starting with the title. No preamble or meta-commentary."""

# Job status lives in Redis (shared across all uvicorn workers) and expires
# natively after JOB_TTL_SECONDS — long enough for Knowledge.jsx's 3s poll
# loop to observe the final status after completion.
JOB_TTL_SECONDS = 3600  # 1 hour


def _job_key(job_id: str) -> str:
    return f"rag:job:{job_id}"


async def _set_job_status(job_id: str, status: dict) -> None:
    await session_store.set_json(_job_key(job_id), status, JOB_TTL_SECONDS)


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
    await _set_job_status(job_id, {"status": "processing", "filename": file.filename})

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
        await _set_job_status(job_id, {"status": "completed", "filename": filename, **result})
    except Exception as e:
        await _set_job_status(job_id, {"status": "failed", "filename": filename, "error": str(e)})


# ── Ingest plain text ─────────────────────────────────────────────────────────

class TextIngestRequest(BaseModel):
    text: str
    category: str = "notes"
    property_id: Optional[str] = None
    title: Optional[str] = None


@router.post("/ingest/text")
async def ingest_text_endpoint(
    background_tasks: BackgroundTasks,
    body: TextIngestRequest,
    current_user: CurrentUser,
    company_id: CompanyId,
):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    job_id = str(uuid4())
    filename = body.title or "pasted_text"
    await _set_job_status(job_id, {"status": "processing", "filename": filename})

    background_tasks.add_task(
        _run_ingest_text,
        job_id, body.text, company_id, body.title, body.category, body.property_id,
    )

    return {"job_id": job_id, "filename": filename, "status": "processing"}


async def _run_ingest_text(job_id, text, company_id, title, category, property_id):
    filename = title or "pasted_text"
    try:
        result = await ingest_text(
            text=text,
            company_id=company_id,
            metadata={
                "source_type": "text_paste",
                "property_id": property_id or "",
                "doc_category": category,
                "filename": filename,
            },
        )
        await _set_job_status(job_id, {"status": "completed", "filename": filename, **result})
    except Exception as e:
        await _set_job_status(job_id, {"status": "failed", "filename": filename, "error": str(e)})


# ── Job status ────────────────────────────────────────────────────────────────

@router.get("/status/{job_id}")
async def get_job_status(job_id: str, current_user: CurrentUser):
    status = await session_store.get_json(_job_key(job_id))
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
async def list_documents(
    company_id: CompanyId,
    accessible_company_ids: AccessibleCompanyIds,
    current_user: CurrentUser,
    filter_company_id: Optional[str] = Query(None, description="Narrow to one child company id"),
):
    ids = [filter_company_id] if filter_company_id and filter_company_id in accessible_company_ids else accessible_company_ids
    sb = get_supabase_admin()
    result = (
        sb.table("documents")
        .select("*")
        .in_("company_id", ids)
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


# ── Voice ingest ──────────────────────────────────────────────────────────────

@router.post("/ingest/voice")
async def ingest_voice(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    company_id: CompanyId,
    audio: UploadFile = File(...),
    category: str = Form(default="notes"),
    title: Optional[str] = Form(default=None),
):
    audio_bytes = await audio.read()
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large (max 25MB)")

    job_id = str(uuid4())
    label = title or "Voice note"
    await _set_job_status(job_id, {"status": "transcribing", "filename": label})

    background_tasks.add_task(
        _run_ingest_voice,
        job_id, audio_bytes, audio.filename or "recording.webm",
        company_id, category, title, current_user["id"],
    )

    return {"job_id": job_id, "filename": label, "status": "transcribing"}


async def _run_ingest_voice(job_id, audio_bytes, filename, company_id, category, title, user_id):
    label = title or "Voice note"
    try:
        import openai as _openai
        s = get_settings()
        client = _openai.AsyncOpenAI(api_key=s.LLM_API_KEY)

        # Transcribe with Whisper
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, audio_bytes, "audio/webm"),
            response_format="text",
        )
        transcript = str(response).strip()

        if not transcript:
            await _set_job_status(job_id, {"status": "failed", "filename": label, "error": "No speech detected"})
            return

        # Purify: clean up speech into structured KB content
        purified = await complete(
            system=PURIFY_SYSTEM,
            messages=[{"role": "user", "content": transcript}],
            max_tokens=1500,
            temperature=0.2,
        )

        # Use first line as document title if not provided
        lines = purified.strip().splitlines()
        doc_title = title or (lines[0].strip("#").strip() if lines else label)

        await ingest_text(
            text=purified,
            company_id=company_id,
            metadata={
                "source_type": "voice_recording",
                "doc_category": category,
                "filename": doc_title,
            },
        )

        await _set_job_status(job_id, {"status": "completed", "filename": doc_title})
    except Exception as e:
        await _set_job_status(job_id, {"status": "failed", "filename": label, "error": str(e)})
