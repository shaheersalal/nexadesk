from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.middleware import CurrentUser, CompanyId
from app.dependencies import get_supabase_admin

router = APIRouter()

# Onboarding is intentionally just two questions — lead source(s) and the AI
# persona name. Everything else (working hours, ai_persona blurb, tone, areas,
# pricing) uses the product-wide defaults already set on the companies table
# and can be edited later from Settings.

LEAD_SOURCE_OPTIONS = [
    "property_portal_ads",   # Bayut, Property Finder, etc.
    "facebook_instagram_ads",
    "google_ads",
    "website_organic",
    "referrals",
    "walk_in",
    "other",
]


class OnboardingCompleteRequest(BaseModel):
    lead_sources: list[str] = []
    receptionist_name: Optional[str] = None


@router.get("/options")
async def onboarding_options():
    """Lead source choices for the onboarding form."""
    return {"lead_sources": LEAD_SOURCE_OPTIONS}


@router.post("/complete")
async def onboarding_complete(
    body: OnboardingCompleteRequest,
    company_id: CompanyId,
    current_user: CurrentUser,
):
    sb = get_supabase_admin()
    receptionist_name = (body.receptionist_name or "").strip() or "Nexa"

    update_payload = {
        "receptionist_name": receptionist_name,
        "onboarding_data": {"lead_sources": body.lead_sources},
        "onboarding_complete": True,
    }

    sb.table("companies").update(update_payload).eq("id", company_id).execute()

    return {"status": "ok", "receptionist_name": receptionist_name}
