from typing import Optional
from uuid import UUID
from datetime import datetime, timezone, date

from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
from fastapi.responses import RedirectResponse

from app.dependencies import RlsDb
from app.auth.middleware import CurrentUser, CompanyId, AccessibleCompanyIds
from app.config import get_settings
from app.dependencies import get_supabase_admin
from app.integrations.events import fire_event
from app.leads.models import (
    LeadCreate, LeadUpdate, LeadStatusUpdate,
    AppointmentCreate, AppointmentUpdate,
    AnalyticsResponse,
)
from app.leads.calendar import create_event, delete_event, get_auth_url, exchange_code

router = APIRouter()




def _resolve_ids(accessible: list[str], filter_id: Optional[str]) -> list[str]:
    """If filter_id is provided and is within the accessible set, narrow to it; else use all."""
    if filter_id and filter_id in accessible:
        return [filter_id]
    return accessible


# ── Leads CRUD ────────────────────────────────────────────────────────────────

@router.get("/")
async def list_leads(
    db: RlsDb,
    company_id: CompanyId,
    accessible_company_ids: AccessibleCompanyIds,
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    source: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0, le=50000),
    filter_company_id: Optional[str] = Query(None, description="Narrow to one child company id"),
):
    ids = _resolve_ids(accessible_company_ids, filter_company_id)
    q = db.table("leads").select("*, conversations(id, channel, started_at)").in_("company_id", ids)
    if status_filter:
        q = q.eq("status", status_filter)
    if source:
        q = q.eq("source", source)
    result = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return result.data


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_lead(body: LeadCreate, db: RlsDb, company_id: CompanyId, current_user: CurrentUser):
    row = body.model_dump()
    row["company_id"] = company_id
    if row.get("assigned_to"):
        row["assigned_to"] = str(row["assigned_to"])
    result = db.table("leads").insert(row).execute()
    lead = result.data[0]
    fire_event(company_id, "lead.created", lead)
    return lead


@router.get("/{lead_id}")
async def get_lead(lead_id: UUID, db: RlsDb, company_id: CompanyId, current_user: CurrentUser):
    result = (
        db.table("leads")
        .select("*, conversations(*), appointments(*)")
        .eq("id", str(lead_id))
        .eq("company_id", company_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return result.data


@router.patch("/{lead_id}")
async def update_lead(lead_id: UUID, body: LeadUpdate, db: RlsDb, company_id: CompanyId, current_user: CurrentUser):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "assigned_to" in updates and updates["assigned_to"]:
        updates["assigned_to"] = str(updates["assigned_to"])
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = (
        db.table("leads").update(updates)
        .eq("id", str(lead_id)).eq("company_id", company_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return result.data[0]


@router.patch("/{lead_id}/status")
async def update_lead_status(lead_id: UUID, body: LeadStatusUpdate, db: RlsDb, company_id: CompanyId, current_user: CurrentUser):
    result = (
        db.table("leads")
        .update({"status": body.status, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", str(lead_id)).eq("company_id", company_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = result.data[0]
    fire_event(company_id, "lead.status_changed", {"id": str(lead_id), "status": body.status, **lead})
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(lead_id: UUID, db: RlsDb, company_id: CompanyId, current_user: CurrentUser):
    db.table("leads").delete().eq("id", str(lead_id)).eq("company_id", company_id).execute()


# ── Appointments ──────────────────────────────────────────────────────────────

@router.get("/appointments/upcoming")
async def list_appointments(
    db: RlsDb,
    company_id: CompanyId,
    accessible_company_ids: AccessibleCompanyIds,
    current_user: CurrentUser,
    from_date: Optional[date] = None,
    limit: int = Query(20, le=100),
    filter_company_id: Optional[str] = Query(None, description="Narrow to one child company id"),
):
    ids = _resolve_ids(accessible_company_ids, filter_company_id)
    q = db.table("appointments").select("*, leads(name, phone), properties(title, address)").in_("company_id", ids)
    if from_date:
        q = q.gte("datetime", from_date.isoformat())
    else:
        q = q.gte("datetime", datetime.now(timezone.utc).isoformat())
    result = q.order("datetime").limit(limit).execute()
    return result.data


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
async def create_appointment(body: AppointmentCreate, db: RlsDb, company_id: CompanyId, current_user: CurrentUser):
    sb = db
    row = body.model_dump()
    row["company_id"] = company_id
    row["datetime"] = row["datetime"].isoformat()
    for field in ("lead_id", "property_id", "agent_id"):
        if row.get(field):
            row[field] = str(row[field])

    # The lead must belong to the caller's company.
    #
    # lead_id arrives in the request body, and neither this read nor the status
    # update below was scoped — so an authenticated user of one agency could
    # pass another agency's lead id and both read that lead's name and email
    # (which then receives the calendar invite) and write to it. The backend
    # uses the service-role client and bypasses RLS, so nothing else was
    # stopping it. Tenant isolation here rests entirely on this filter.
    lead = (
        sb.table("leads").select("name, email")
        .eq("id", row["lead_id"]).eq("company_id", company_id)
        .maybe_single().execute()
    )
    if not lead or not lead.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead_data = lead.data
    summary = f"Property Showing — {lead_data.get('name', 'Guest')}"
    google_id = await create_event(
        company_id=company_id,
        summary=summary,
        start_dt=body.datetime,
        duration_minutes=body.duration_minutes,
        attendee_email=lead_data.get("email"),
    )
    if google_id:
        row["google_event_id"] = google_id

    result = sb.table("appointments").insert(row).execute()
    appt = result.data[0]

    # Update lead status to 'appointment' — scoped for the same reason as above.
    (
        sb.table("leads").update({"status": "appointment"})
        .eq("id", row["lead_id"]).eq("company_id", company_id).execute()
    )

    fire_event(company_id, "appointment.booked", appt)
    return appt


@router.patch("/appointments/{appt_id}")
async def update_appointment(appt_id: UUID, body: AppointmentUpdate, db: RlsDb, company_id: CompanyId, current_user: CurrentUser):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "datetime" in updates:
        updates["datetime"] = updates["datetime"].isoformat()
    result = (
        db.table("appointments").update(updates)
        .eq("id", str(appt_id)).eq("company_id", company_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return result.data[0]


@router.delete("/appointments/{appt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(appt_id: UUID, db: RlsDb, company_id: CompanyId, current_user: CurrentUser):
    sb = db
    # Scoped: unfiltered, this both confirmed another tenant's appointment
    # exists and handed its google_event_id to delete_event() under this
    # company's credentials.
    appt = (
        sb.table("appointments").select("google_event_id")
        .eq("id", str(appt_id)).eq("company_id", company_id)
        .maybe_single().execute()
    )
    if appt and appt.data and appt.data.get("google_event_id"):
        await delete_event(company_id, appt.data["google_event_id"])
    sb.table("appointments").delete().eq("id", str(appt_id)).eq("company_id", company_id).execute()


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics/summary")
async def get_analytics(
    db: RlsDb,
    company_id: CompanyId,
    accessible_company_ids: AccessibleCompanyIds,
    current_user: CurrentUser,
    filter_company_id: Optional[str] = Query(None, description="Narrow to one child company id"),
):
    sb = db
    # UTC, not the server's local date: on a Railway container in a different
    # region than the user, date.today() rolls over at the wrong moment and
    # "today's appointments" silently shifts by a day.
    today = datetime.now(timezone.utc).date().isoformat()
    ids = _resolve_ids(accessible_company_ids, filter_company_id)

    leads = sb.table("leads").select("source, status, score").in_("company_id", ids).execute()
    leads_data = leads.data or []

    conversations = sb.table("conversations").select("channel").in_("company_id", ids).execute()
    conv_data = conversations.data or []

    appointments = (
        sb.table("appointments").select("id")
        .in_("company_id", ids)
        .gte("datetime", datetime.now(timezone.utc).isoformat())
        .eq("status", "scheduled")
        .execute()
    )

    leads_today_count = len(
        sb.table("leads").select("id").in_("company_id", ids).gte("created_at", today).execute().data or []
    )

    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    scores = []
    for lead in leads_data:
        by_source[lead["source"]] = by_source.get(lead["source"], 0) + 1
        by_status[lead["status"]] = by_status.get(lead["status"], 0) + 1
        scores.append(lead.get("score", 0))

    by_channel: dict[str, int] = {}
    for conv in conv_data:
        by_channel[conv["channel"]] = by_channel.get(conv["channel"], 0) + 1

    return {
        "total_leads": len(leads_data),
        "leads_by_source": by_source,
        "leads_by_status": by_status,
        "leads_today": leads_today_count,
        "appointments_upcoming": len(appointments.data or []),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "total_conversations": len(conv_data),
        "conversations_by_channel": by_channel,
    }


# ── Google Calendar OAuth ─────────────────────────────────────────────────────

@router.get("/calendar/connect")
async def calendar_connect(current_user: CurrentUser):
    if not get_settings().GOOGLE_CALENDAR_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Google Calendar not configured")
    return {"auth_url": get_auth_url()}


@router.get("/calendar/callback")
async def calendar_callback(code: str, company_id: CompanyId, current_user: CurrentUser):
    success = await exchange_code(code, company_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth code")
    return {"status": "Google Calendar connected"}
