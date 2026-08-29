"""
Webhook management endpoints.
GET/POST/PATCH/DELETE /integrations/webhooks
POST /integrations/webhooks/{id}/test
GET  /integrations/webhooks/{id}/logs
"""
import secrets
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.auth.middleware import CurrentUser, CompanyId
from app.dependencies import RlsDb
from app.integrations.events import EVENTS, fire_event

router = APIRouter()




# ── Models ────────────────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    url: HttpUrl
    events: list[str]

    def validate_events(self):
        invalid = [e for e in self.events if e not in EVENTS]
        if invalid:
            raise HTTPException(400, f"Unknown events: {invalid}. Valid: {sorted(EVENTS)}")


class WebhookUpdate(BaseModel):
    url: HttpUrl | None = None
    events: list[str] | None = None
    active: bool | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/webhooks")
async def list_webhooks(db: RlsDb, company_id: CompanyId, _: CurrentUser):
    result = db.table("webhook_endpoints").select("id,url,events,active,created_at") \
        .eq("company_id", company_id).order("created_at", desc=True).execute()
    return result.data or []


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
async def create_webhook(body: WebhookCreate, db: RlsDb, company_id: CompanyId, _: CurrentUser):
    body.validate_events()
    secret = secrets.token_hex(32)
    result = db.table("webhook_endpoints").insert({
        "company_id": company_id,
        "url": str(body.url),
        "events": body.events,
        "secret": secret,
        "active": True,
    }).execute()
    row = result.data[0]
    # Return secret once — never shown again
    return {**row, "secret": secret, "secret_hint": "Save this — it will not be shown again."}


@router.patch("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: UUID, body: WebhookUpdate, db: RlsDb, company_id: CompanyId, _: CurrentUser):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "url" in updates:
        updates["url"] = str(updates["url"])
    if not updates:
        raise HTTPException(400, "Nothing to update")
    result = db.table("webhook_endpoints").update(updates) \
        .eq("id", str(webhook_id)).eq("company_id", company_id).execute()
    if not result.data:
        raise HTTPException(404, "Webhook not found")
    return result.data[0]


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(webhook_id: UUID, db: RlsDb, company_id: CompanyId, _: CurrentUser):
    db.table("webhook_endpoints").delete() \
        .eq("id", str(webhook_id)).eq("company_id", company_id).execute()


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: UUID, db: RlsDb, company_id: CompanyId, _: CurrentUser):
    result = db.table("webhook_endpoints").select("*") \
        .eq("id", str(webhook_id)).eq("company_id", company_id).single().execute()
    if not result.data:
        raise HTTPException(404, "Webhook not found")
    fire_event(company_id, "lead.created", {
        "id": "test-00000000-0000-0000-0000-000000000000",
        "name": "Test Lead",
        "phone": "+1 555 000 0000",
        "email": "test@example.com",
        "source": "webhook_test",
        "status": "new",
        "score": 72,
        "_test": True,
    })
    return {"status": "test event fired"}


@router.get("/webhooks/{webhook_id}/logs")
async def get_webhook_logs(webhook_id: UUID, db: RlsDb, company_id: CompanyId, _: CurrentUser):
    # Verify ownership
    ep = db.table("webhook_endpoints").select("id") \
        .eq("id", str(webhook_id)).eq("company_id", company_id).single().execute()
    if not ep.data:
        raise HTTPException(404, "Webhook not found")
    logs = db.table("webhook_logs").select(
        "id,event,status_code,attempts,delivered_at,next_retry_at,error,created_at"
    ).eq("endpoint_id", str(webhook_id)).order("created_at", desc=True).limit(50).execute()
    return logs.data or []
