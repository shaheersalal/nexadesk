"""
NexaDesk Public API v1 — authenticated with API keys.
Authorization: Bearer nxd_live_...

GET  /v1/leads
POST /v1/leads
GET  /v1/appointments
GET  /v1/properties
"""
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.dependencies import get_supabase_admin

router = APIRouter()


def _sb():
    return get_supabase_admin()


# Debounce the last_used write. Previously every authenticated read triggered a
# write to api_keys, doubling round-trips and churning rows (AUDIT.md M10).
_LAST_USED_DEBOUNCE = 300  # seconds
_last_used_seen: dict[str, float] = {}


def _touch_last_used(sb, key_hash: str) -> None:
    now = time.monotonic()
    seen = _last_used_seen.get(key_hash)
    if seen is not None and now - seen < _LAST_USED_DEBOUNCE:
        return
    _last_used_seen[key_hash] = now
    try:
        sb.table("api_keys").update(
            {"last_used": datetime.now(timezone.utc).isoformat()}
        ).eq("key_hash", key_hash).execute()
    except Exception:
        pass  # Telemetry only — never fail a request over it


async def _validate_api_key(request: Request) -> dict:
    """Validate Bearer nxd_live_... key; return {company_id, scopes}."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer nxd_"):
        raise HTTPException(status_code=401, detail="Valid API key required: Authorization: Bearer nxd_live_...")

    raw_key = auth.removeprefix("Bearer ").strip()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    sb = _sb()
    # maybe_single(), not single(): supabase-py raises on no-match with single(),
    # which turned every wrong or rotated key into an opaque HTTP 500 instead of
    # a 401 (AUDIT.md H4).
    result = sb.table("api_keys").select("company_id,scopes,revoked_at") \
        .eq("key_hash", key_hash).maybe_single().execute()

    if not result or not result.data:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if result.data.get("revoked_at"):
        raise HTTPException(status_code=401, detail="API key has been revoked")

    _touch_last_used(sb, key_hash)

    return {
        "company_id": result.data["company_id"],
        # A NULL scopes column would otherwise raise TypeError on the
        # `in` checks below.
        "scopes": result.data.get("scopes") or [],
    }


class LeadIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    source: str = "api"
    notes: Optional[str] = None


@router.get("/leads")
async def v1_list_leads(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    auth = await _validate_api_key(request)
    if "leads:read" not in auth["scopes"]:
        raise HTTPException(403, "Scope 'leads:read' required")
    q = _sb().table("leads").select("id,name,email,phone,status,source,score,created_at") \
        .eq("company_id", auth["company_id"])
    if status_filter:
        q = q.eq("status", status_filter)
    result = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return {"data": result.data or [], "count": len(result.data or [])}


@router.post("/leads", status_code=status.HTTP_201_CREATED)
async def v1_create_lead(request: Request, body: LeadIn):
    auth = await _validate_api_key(request)
    if "leads:write" not in auth["scopes"]:
        raise HTTPException(403, "Scope 'leads:write' required")
    result = _sb().table("leads").insert({
        "company_id": auth["company_id"],
        "name": body.name,
        "email": body.email,
        "phone": body.phone,
        "source": body.source,
        "notes": body.notes,
        "status": "new",
    }).execute()
    if not result.data:
        # Insert returned no representation (RLS, trigger, or minimal return) —
        # IndexError here used to surface as a 500 (AUDIT.md M12).
        raise HTTPException(500, "Lead was not created")
    lead = result.data[0]
    from app.integrations.events import fire_event
    fire_event(auth["company_id"], "lead.created", lead)
    return lead


@router.get("/appointments")
async def v1_list_appointments(request: Request, limit: int = Query(20, le=100)):
    auth = await _validate_api_key(request)
    if "appointments:read" not in auth["scopes"]:
        raise HTTPException(403, "Scope 'appointments:read' required")
    result = _sb().table("appointments") \
        .select("id,datetime,status,notes,leads(name,phone),properties(title,address)") \
        .eq("company_id", auth["company_id"]) \
        .gte("datetime", datetime.now(timezone.utc).isoformat()) \
        .order("datetime").limit(limit).execute()
    return {"data": result.data or []}


@router.get("/properties")
async def v1_list_properties(
    request: Request,
    limit: int = Query(50, le=200),
    property_type: Optional[str] = Query(None, alias="type"),
):
    auth = await _validate_api_key(request)
    if "properties:read" not in auth["scopes"]:
        raise HTTPException(403, "Scope 'properties:read' required")
    q = _sb().table("properties").select("id,title,address,type,price,status,bedrooms,bathrooms") \
        .eq("company_id", auth["company_id"])
    if property_type:
        q = q.eq("type", property_type)
    result = q.order("created_at", desc=True).limit(limit).execute()
    return {"data": result.data or []}
