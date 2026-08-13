"""
API key management endpoints.
POST   /integrations/api-keys      → create key (full key returned once)
GET    /integrations/api-keys      → list active keys (prefix only, never full key)
DELETE /integrations/api-keys/{id} → revoke key
"""
import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.middleware import CurrentUser, CompanyId, require_owner_or_admin
from app.dependencies import get_supabase_admin

router = APIRouter()

ALL_SCOPES = ["leads:read", "leads:write", "appointments:read", "properties:read"]

# An API key bypasses the dashboard's permission model entirely, so minting one
# is an owner/admin action. Also bounded, so a compromised account cannot
# create keys indefinitely.
MAX_KEYS_PER_COMPANY = 20


def _sb():
    return get_supabase_admin()


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class KeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["leads:read", "appointments:read"]


@router.get("/api-keys")
async def list_keys(company_id: CompanyId, _: CurrentUser):
    result = _sb().table("api_keys").select(
        "id,name,key_prefix,scopes,last_used,created_at,revoked_at"
    ).eq("company_id", company_id).is_("revoked_at", None).order("created_at", desc=True).execute()
    return result.data or []


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_key(
    body: KeyCreate,
    company_id: CompanyId,
    _admin=Depends(require_owner_or_admin),
):
    """
    Mint an API key. Owner/admin only.

    Previously any authenticated company member could create a key with any
    scope, then use /v1 or /mcp to read and write all company data outside the
    dashboard's permission model (AUDIT.md H8).
    """
    invalid = [s for s in body.scopes if s not in ALL_SCOPES]
    if invalid:
        raise HTTPException(400, f"Invalid scopes: {invalid}. Valid: {ALL_SCOPES}")
    if not body.scopes:
        raise HTTPException(400, "At least one scope is required")

    existing = _sb().table("api_keys").select("id", count="exact") \
        .eq("company_id", company_id).is_("revoked_at", None).execute()
    if (existing.count or 0) >= MAX_KEYS_PER_COMPANY:
        raise HTTPException(
            400,
            f"Key limit reached ({MAX_KEYS_PER_COMPANY}). Revoke an unused key first.",
        )

    raw_key = "nxd_live_" + secrets.token_hex(32)
    key_prefix = raw_key[:16]  # "nxd_live_" + 7 hex chars

    result = _sb().table("api_keys").insert({
        "company_id": company_id,
        "name": body.name,
        "key_hash": _hash_key(raw_key),
        "key_prefix": key_prefix,
        "scopes": body.scopes,
    }).execute()

    if not result.data:
        raise HTTPException(500, "API key was not created")
    row = result.data[0]
    return {**row, "key": raw_key, "key_hint": "Save this — it will not be shown again."}


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(key_id: str, company_id: CompanyId, _: CurrentUser):
    result = _sb().table("api_keys").update({
        "revoked_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", key_id).eq("company_id", company_id).is_("revoked_at", None).execute()
    if not result.data:
        raise HTTPException(404, "API key not found or already revoked")
