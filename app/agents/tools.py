"""
Shared tools called by individual agents in the orchestrator.
Each function is self-contained — no circular imports with engine.py.
"""
import json
from typing import Optional

from app.dependencies import get_supabase_admin
from app.shared.verticals import get_vertical


async def capture_lead_fields(
    lead_id: Optional[str],
    company_id: str,
    *,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    budget_min: Optional[int] = None,
    budget_max: Optional[int] = None,
    area_preference: Optional[str] = None,
    bedrooms_needed: Optional[int] = None,
    timeline: Optional[str] = None,
    intent: Optional[str] = None,
    # ai_studio-vertical fields (migration 0006_leads_studio_fields.sql) —
    # unset for real_estate leads, which keep using the fields above.
    client_company: Optional[str] = None,
    project_type: Optional[str] = None,
    budget_text: Optional[str] = None,
) -> Optional[str]:
    """
    Upsert structured lead fields into Supabase.
    Creates a new lead row if lead_id is None.
    Returns the lead_id (existing or newly created).
    """
    updates = {k: v for k, v in {
        "name": name,
        "phone": phone,
        "email": email,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "area_preference": area_preference,
        "bedrooms_needed": bedrooms_needed,
        "timeline": timeline,
        "intent": intent,
        "client_company": client_company,
        "project_type": project_type,
        "budget_text": budget_text,
    }.items() if v is not None}

    if not updates:
        return lead_id

    sb = get_supabase_admin()
    try:
        if lead_id:
            sb.table("leads").update(updates).eq("id", lead_id).eq("company_id", company_id).execute()
        else:
            updates["company_id"] = company_id
            updates["source"] = "chat"
            updates["status"] = "new"
            result = sb.table("leads").insert(updates).execute()
            lead_id = (result.data or [{}])[0].get("id")
    except Exception:
        pass

    return lead_id


async def flag_escalation(lead_id: Optional[str], company_id: str) -> None:
    """Mark a lead as needing human follow-up."""
    if not lead_id:
        return
    try:
        sb = get_supabase_admin()
        sb.table("leads").update({"needs_human": True, "status": "contacted"}).eq("id", lead_id).eq("company_id", company_id).execute()
    except Exception:
        pass


async def extract_fields_from_message(
    query: str,
    llm_complete_fn,
    vertical_key: Optional[str] = None,
) -> dict:
    """
    Fast gpt-4o-mini call to pull structured facts from a single user message.
    Returns a dict with nulls for anything not mentioned. The fields extracted
    depend on the company's vertical (app/shared/verticals.py) — real_estate
    pulls budget_min/max + bedrooms, ai_studio pulls client_company +
    project_type, etc. Falls back to real_estate for anything unset.
    """
    prompt = get_vertical(vertical_key)["extract_prompt"].format(query=query)
    raw = await llm_complete_fn(
        system="Extract facts from a message. Return only valid JSON.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.0,
    )
    try:
        # Strip markdown code fences if present
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)
    except Exception:
        return {}
