"""
CRM OAuth consumer routes.
GET    /integrations/crm/connections        → list connected CRMs
GET    /integrations/crm/connect/{provider} → start OAuth, returns {auth_url}
GET    /integrations/crm/callback/{provider}→ OAuth callback (browser redirect)
DELETE /integrations/crm/{provider}         → disconnect
POST   /integrations/crm/sync/{provider}    → manual sync last 50 leads
"""
import logging
import secrets
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.auth.middleware import CurrentUser, CompanyId
from app.config import get_settings, Settings
from app.dependencies import get_supabase_admin, get_redis
from app.shared.crypto import decrypt, encrypt
from app.integrations.crm import hubspot, zoho

logger = logging.getLogger("nexadesk.integrations.crm")
router = APIRouter()


def _sb():
    return get_supabase_admin()


PROVIDERS = {
    "hubspot": {
        "name": "HubSpot",
        "module": hubspot,
        "client_id_attr": "HUBSPOT_CLIENT_ID",
        "client_secret_attr": "HUBSPOT_CLIENT_SECRET",
    },
    "zoho": {
        "name": "Zoho CRM",
        "module": zoho,
        "client_id_attr": "ZOHO_CLIENT_ID",
        "client_secret_attr": "ZOHO_CLIENT_SECRET",
    },
}


def _redirect_uri(provider: str, settings: Settings) -> str:
    return f"{settings.APP_BASE_URL}/integrations/crm/callback/{provider}"


def _dashboard_url(settings: Settings, **params) -> str:
    base = settings.DASHBOARD_URL
    if params:
        from urllib.parse import urlencode
        return f"{base}/dashboard/integrations?{urlencode(params)}"
    return f"{base}/dashboard/integrations"


@router.get("/crm/connections")
async def list_connections(company_id: CompanyId, _: CurrentUser):
    result = _sb().table("crm_connections").select(
        "id,provider,account_name,account_id,scope,created_at,updated_at"
    ).eq("company_id", company_id).execute()
    return result.data or []


@router.get("/crm/connect/{provider}")
async def crm_connect(
    provider: str,
    company_id: CompanyId,
    _: CurrentUser,
    redis: aioredis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
):
    p = PROVIDERS.get(provider)
    if not p:
        raise HTTPException(400, f"Unknown provider '{provider}'. Supported: {list(PROVIDERS)}")

    client_id = getattr(settings, p["client_id_attr"])
    if not client_id:
        raise HTTPException(503, f"{p['name']} not configured — add {p['client_id_attr']} to your environment")

    state = secrets.token_urlsafe(32)
    await redis.set(f"crm_state:{state}", company_id, ex=600)

    auth_url = p["module"].build_auth_url(client_id, _redirect_uri(provider, settings), state)
    return {"auth_url": auth_url, "provider": provider, "provider_name": p["name"]}


@router.get("/crm/callback/{provider}")
async def crm_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    redis: aioredis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
):
    p = PROVIDERS.get(provider)
    if not p:
        return RedirectResponse(_dashboard_url(settings, error="unknown_provider"), status_code=302)

    company_id = await redis.get(f"crm_state:{state}")
    if not company_id:
        return RedirectResponse(_dashboard_url(settings, error="state_expired"), status_code=302)
    await redis.delete(f"crm_state:{state}")

    client_id = getattr(settings, p["client_id_attr"])
    client_secret = getattr(settings, p["client_secret_attr"])

    try:
        tokens = await p["module"].exchange_code(
            code, client_id, client_secret, _redirect_uri(provider, settings)
        )
    except Exception as exc:
        logger.error("CRM token exchange failed for %s: %s", provider, exc)
        return RedirectResponse(_dashboard_url(settings, error="auth_failed"), status_code=302)

    # Fetch account display info
    account_id, account_name = "", ""
    try:
        if provider == "hubspot":
            info = await hubspot.get_portal_info(tokens["access_token"])
            account_id = str(info.get("portalId", ""))
            account_name = info.get("domain", "HubSpot Portal")
        elif provider == "zoho":
            info = await zoho.get_org_info(tokens["access_token"])
            account_id = str(info.get("id", ""))
            account_name = info.get("company_name", "Zoho Org")
    except Exception:
        pass

    expires_at = None
    if tokens.get("expires_in"):
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])).isoformat()

    _sb().table("crm_connections").upsert({
        "company_id": company_id,
        "provider": provider,
        # Encrypted at rest — see app/shared/crypto.py (AUDIT.md H9).
        "access_token": encrypt(tokens["access_token"]),
        "refresh_token": encrypt(tokens.get("refresh_token")),
        "expires_at": expires_at,
        "scope": tokens.get("scope"),
        "account_id": account_id,
        "account_name": account_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="company_id,provider").execute()

    logger.info("CRM connected: %s for company %s (%s)", provider, company_id, account_name)
    return RedirectResponse(_dashboard_url(settings, connected=provider), status_code=302)


@router.delete("/crm/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def crm_disconnect(provider: str, company_id: CompanyId, _: CurrentUser):
    if provider not in PROVIDERS:
        raise HTTPException(400, "Unknown provider")
    _sb().table("crm_connections").delete() \
        .eq("company_id", company_id).eq("provider", provider).execute()


@router.post("/crm/sync/{provider}")
async def crm_sync(
    provider: str,
    company_id: CompanyId,
    _: CurrentUser,
    settings: Settings = Depends(get_settings),
):
    p = PROVIDERS.get(provider)
    if not p:
        raise HTTPException(400, "Unknown provider")

    conn = _sb().table("crm_connections").select("*") \
        .eq("company_id", company_id).eq("provider", provider).single().execute()
    if not conn.data:
        raise HTTPException(404, f"No {p['name']} connection found. Connect it first.")

    token = decrypt(conn.data["access_token"])
    stored_refresh = decrypt(conn.data.get("refresh_token"))

    # Refresh token if expiring soon
    if conn.data.get("expires_at") and stored_refresh:
        expires = datetime.fromisoformat(conn.data["expires_at"])
        if expires < datetime.now(timezone.utc) + timedelta(minutes=5):
            try:
                new_tokens = await p["module"].refresh_access_token(
                    stored_refresh,
                    getattr(settings, p["client_id_attr"]),
                    getattr(settings, p["client_secret_attr"]),
                )
                token = new_tokens["access_token"]
                _sb().table("crm_connections").update({
                    "access_token": encrypt(token),
                    "refresh_token": encrypt(new_tokens.get("refresh_token", stored_refresh)),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=new_tokens.get("expires_in", 3600))).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", conn.data["id"]).execute()
            except Exception as exc:
                raise HTTPException(502, f"Token refresh failed: {exc}")

    leads = _sb().table("leads").select("*") \
        .eq("company_id", company_id).order("created_at", desc=True).limit(50).execute()

    synced, errors = 0, 0
    for lead in (leads.data or []):
        try:
            await p["module"].sync_lead(lead, token)
            synced += 1
        except Exception as exc:
            logger.warning("Sync error for lead %s: %s", lead.get("id"), exc)
            errors += 1

    return {"provider": provider, "synced": synced, "errors": errors}
