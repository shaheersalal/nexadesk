from typing import Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID


class LeadCreate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source: str = "manual"
    status: str = "new"
    score: int = 0
    notes: Optional[str] = None
    language: str = "en"
    assigned_to: Optional[UUID] = None
    # Qualifier Agent fields
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    area_preference: Optional[str] = None
    bedrooms_needed: Optional[int] = None
    timeline: Optional[str] = None
    intent: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    score: Optional[int] = None
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None
    # Qualifier Agent fields
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    area_preference: Optional[str] = None
    bedrooms_needed: Optional[int] = None
    timeline: Optional[str] = None
    intent: Optional[str] = None
    needs_human: Optional[bool] = None


class LeadStatusUpdate(BaseModel):
    status: str  # new|contacted|qualified|appointment|closed_won|closed_lost


class AppointmentCreate(BaseModel):
    lead_id: UUID
    property_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    datetime: datetime
    duration_minutes: int = 30
    type: str = "showing"
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    datetime: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    type: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class AnalyticsResponse(BaseModel):
    total_leads: int
    leads_by_source: dict[str, int]
    leads_by_status: dict[str, int]
    leads_today: int
    appointments_upcoming: int
    avg_score: float
    total_conversations: int
    conversations_by_channel: dict[str, int]
