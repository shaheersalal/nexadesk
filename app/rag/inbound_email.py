"""
Email-forward listing ingestion: a per-company inbound address
(listings+{company_id}@<receiving-domain>) routes Resend's "email.received"
webhook into the same RAG pipeline used for dashboard uploads, instead of
building a separate ingestion path.

Resend's webhook payload carries metadata only — no body or attachment
content (https://resend.com/docs/dashboard/receiving/introduction). Full
content is fetched via two follow-up calls to the Resend Received Emails /
Attachments API, then handed to the same ingest_file/ingest_text functions
the dashboard upload and voice-note routes already use.
"""
import base64
import hashlib
import hmac
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.dependencies import get_supabase_admin
from app.rag.pipeline import ingest_file, ingest_text

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("nexadesk.rag.inbound_email")

RESEND_API_BASE = "https://api.resend.com"
COMPANY_ADDRESS_RE = re.compile(r"listings\+([a-zA-Z0-9-]+)@")

# Inline images (logos, signature avatars) are skipped — agents aren't
# expected to attach those as listings, and ingesting every embedded image
# in a forwarded email would add noise to the knowledge base.
INGESTIBLE_CONTENT_TYPES = {
    "text/csv", "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png", "image/jpeg", "image/jpg",
}


def _extract_company_id(addresses: list[str]) -> Optional[str]:
    for addr in addresses:
        m = COMPANY_ADDRESS_RE.search(addr or "")
        if m:
            return m.group(1)
    return None


def _verify_signature(request_body: bytes, headers: dict) -> bool:
    """Svix HMAC verification, the scheme Resend uses for all webhooks."""
    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        return True  # not configured yet -- dev mode, mirrors voice/router.py's Twilio skip pattern

    svix_id = headers.get("svix-id", "")
    svix_timestamp = headers.get("svix-timestamp", "")
    svix_signature = headers.get("svix-signature", "")
    if not (svix_id and svix_timestamp and svix_signature):
        return False

    signed_content = f"{svix_id}.{svix_timestamp}.{request_body.decode()}"
    secret_bytes = base64.b64decode(secret.removeprefix("whsec_"))
    expected = base64.b64encode(
        hmac.new(secret_bytes, signed_content.encode(), hashlib.sha256).digest()
    ).decode()

    for part in svix_signature.split(" "):
        if "," not in part:
            continue
        _, sig = part.split(",", 1)
        if hmac.compare_digest(sig, expected):
            return True
    return False


async def _fetch_received_email(email_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{RESEND_API_BASE}/emails/receiving/{email_id}",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()


async def _fetch_attachment_bytes(email_id: str, attachment_id: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0) as client:
        meta_resp = await client.get(
            f"{RESEND_API_BASE}/emails/receiving/{email_id}/attachments/{attachment_id}",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
        meta_resp.raise_for_status()
        download_url = meta_resp.json().get("download_url")
        if not download_url:
            return b""
        file_resp = await client.get(download_url)
        file_resp.raise_for_status()
        return file_resp.content


@router.post("/inbound-email")
async def inbound_email(request: Request):
    """
    Resend webhook target for the per-company listings inbound address.
    Configure this URL as the Resend webhook endpoint for `email.received` events.
    """
    raw_body = await request.body()
    if not _verify_signature(raw_body, dict(request.headers)):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    payload = await request.json()
    if payload.get("type") != "email.received":
        return {"status": "ignored"}

    data = payload.get("data", {})
    email_id = data.get("email_id")
    if not email_id:
        return {"status": "ignored"}

    candidate_addresses = (data.get("to") or []) + (data.get("received_for") or [])
    company_id = _extract_company_id(candidate_addresses)
    if not company_id:
        logger.warning(f"Inbound email {email_id} matched no listings+<company_id> address: {candidate_addresses}")
        return {"status": "ignored"}

    sb = get_supabase_admin()
    company = sb.table("companies").select("id").eq("id", company_id).execute()
    if not company.data:
        logger.warning(f"Inbound email {email_id} addressed to unknown company_id {company_id}")
        return {"status": "ignored"}

    full_email = await _fetch_received_email(email_id)
    subject = full_email.get("subject") or "Forwarded listing email"

    ingested_any = False
    for att in full_email.get("attachments", []):
        if att.get("content_type") not in INGESTIBLE_CONTENT_TYPES:
            continue
        try:
            file_bytes = await _fetch_attachment_bytes(email_id, att["id"])
            if not file_bytes:
                continue
            await ingest_file(
                file_bytes=file_bytes,
                filename=att.get("filename") or f"email-attachment-{att['id']}",
                company_id=company_id,
                category="listing",
                uploaded_by=None,
            )
            ingested_any = True
        except Exception as e:
            logger.error(f"Failed to ingest attachment {att.get('id')} from email {email_id}: {e}")

    # Agents sometimes paste listing details straight into the email body
    # instead of attaching a file -- ingest that too when it's substantial.
    body_text = (full_email.get("text") or "").strip()
    if len(body_text) > 40:
        try:
            await ingest_text(
                text=body_text,
                company_id=company_id,
                metadata={
                    "source_type": "email_forward",
                    "doc_category": "listing",
                    "filename": subject,
                },
            )
            ingested_any = True
        except Exception as e:
            logger.error(f"Failed to ingest body text from email {email_id}: {e}")

    return {"status": "ingested" if ingested_any else "no_ingestible_content"}
