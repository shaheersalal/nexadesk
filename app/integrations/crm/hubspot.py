"""HubSpot OAuth consumer: auth URL, token exchange, lead sync."""
import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("nexadesk.crm.hubspot")

AUTH_URL = "https://app.hubspot.com/oauth/authorize"
TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
PORTAL_URL = "https://api.hubapi.com/account-info/v3/details"
API_BASE = "https://api.hubapi.com"
SCOPES = "crm.objects.contacts.write crm.objects.contacts.read crm.objects.deals.write crm.objects.deals.read"

_STATUS_STAGES = {
    "new": "appointmentscheduled",
    "contacted": "qualifiedtobuy",
    "qualified": "presentationscheduled",
    "appointment": "decisionmakerboughtin",
    "closed": "closedwon",
    "lost": "closedlost",
}


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    return f"{AUTH_URL}?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
    })


async def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(TOKEN_URL, data={
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
        r = await c.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        })
        r.raise_for_status()
        return r.json()


async def get_portal_info(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(PORTAL_URL, headers={"Authorization": f"Bearer {access_token}"})
        r.raise_for_status()
        return r.json()


async def sync_lead(lead: dict, access_token: str):
    """Upsert HubSpot Contact + Deal from a NexaDesk lead dict."""
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    name_parts = (lead.get("name") or "").split(None, 1)

    contact_props = {k: v for k, v in {
        "firstname": name_parts[0] if name_parts else "",
        "lastname": name_parts[1] if len(name_parts) > 1 else "",
        "email": lead.get("email") or "",
        "phone": lead.get("phone") or "",
    }.items() if v}

    async with httpx.AsyncClient(timeout=15) as c:
        contact_id = None
        if lead.get("email"):
            r = await c.patch(
                f"{API_BASE}/crm/v3/objects/contacts/{lead['email']}?idProperty=email",
                json={"properties": contact_props}, headers=headers,
            )
            if r.status_code == 200:
                contact_id = r.json()["id"]

        if not contact_id:
            r = await c.post(f"{API_BASE}/crm/v3/objects/contacts",
                             json={"properties": contact_props}, headers=headers)
            if r.status_code in (200, 201):
                contact_id = r.json()["id"]
            else:
                logger.warning("HubSpot contact create failed: %s", r.text)

        stage = _STATUS_STAGES.get(lead.get("status", "new"), "appointmentscheduled")
        deal_r = await c.post(f"{API_BASE}/crm/v3/objects/deals", json={"properties": {
            "dealname": f"{lead.get('name', 'Lead')} — NexaDesk",
            "dealstage": stage,
            "pipeline": "default",
            "description": f"Source: {lead.get('source', 'NexaDesk')} | Score: {lead.get('score', 0)}",
        }}, headers=headers)

        if deal_r.status_code in (200, 201) and contact_id:
            deal_id = deal_r.json()["id"]
            await c.put(
                f"{API_BASE}/crm/v3/associations/deals/contacts/batch/create",
                json={"inputs": [{"from": {"id": deal_id}, "to": {"id": contact_id}, "type": "deal_to_contact"}]},
                headers=headers,
            )
            logger.info("HubSpot synced lead %s (contact %s, deal %s)", lead.get("id"), contact_id, deal_id)
