"""Zoho CRM OAuth consumer: auth URL, token exchange, lead sync."""
import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("nexadesk.crm.zoho")

AUTH_URL = "https://accounts.zoho.com/oauth/v2/auth"
TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
API_BASE = "https://www.zohoapis.com/crm/v2"
SCOPES = "ZohoCRM.modules.Contacts.ALL,ZohoCRM.modules.Leads.ALL"


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    return f"{AUTH_URL}?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "response_type": "code",
        "access_type": "offline",
    })


async def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(TOKEN_URL, params={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        })
        r.raise_for_status()
        return r.json()


async def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(TOKEN_URL, params={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        })
        r.raise_for_status()
        return r.json()


async def get_org_info(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/org",
                        headers={"Authorization": f"Zoho-oauthtoken {access_token}"})
        if r.status_code == 200:
            orgs = r.json().get("org", [{}])
            return orgs[0] if orgs else {}
    return {}


async def sync_lead(lead: dict, access_token: str):
    """Upsert a Zoho CRM Lead from a NexaDesk lead dict."""
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    name_parts = (lead.get("name") or "").split(None, 1)
    data = {k: v for k, v in {
        "First_Name": name_parts[0] if name_parts else "",
        "Last_Name": name_parts[1] if len(name_parts) > 1 else (name_parts[0] if name_parts else "Lead"),
        "Email": lead.get("email"),
        "Phone": lead.get("phone"),
        "Lead_Source": "NexaDesk",
        "Description": f"Score: {lead.get('score', 0)} | Source: {lead.get('source', '')}",
    }.items() if v}

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API_BASE}/Leads", json={"data": [data]}, headers=headers)
        if r.status_code not in (200, 201):
            logger.warning("Zoho lead create failed: %s", r.text)
        else:
            logger.info("Zoho synced lead %s", lead.get("id"))
