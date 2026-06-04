from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from uuid import UUID


class PropertyCreate(BaseModel):
    title: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    property_type: Optional[str] = None  # house|condo|apartment|townhouse|land|commercial
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    price: Optional[Decimal] = None
    status: str = "active"
    description: Optional[str] = None
    features: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    mls_number: Optional[str] = None


class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    price: Optional[Decimal] = None
    status: Optional[str] = None
    description: Optional[str] = None
    features: Optional[list[str]] = None
    images: Optional[list[str]] = None
    mls_number: Optional[str] = None


class PropertyOut(PropertyCreate):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime


def property_to_text(p: dict) -> str:
    """Convert a property record to a plain-text chunk for RAG ingestion."""
    parts = [f"Property: {p.get('title', 'Untitled')}"]
    if p.get("address"):
        loc = ", ".join(filter(None, [p.get("address"), p.get("city"), p.get("state"), p.get("zip")]))
        parts.append(f"Location: {loc}")
    if p.get("property_type"):
        parts.append(f"Type: {p['property_type'].title()}")
    if p.get("bedrooms"):
        parts.append(f"Bedrooms: {p['bedrooms']}")
    if p.get("bathrooms"):
        parts.append(f"Bathrooms: {p['bathrooms']}")
    if p.get("sqft"):
        parts.append(f"Size: {p['sqft']:,} sqft")
    if p.get("price"):
        parts.append(f"Price: ${float(p['price']):,.0f}")
    if p.get("status"):
        parts.append(f"Status: {p['status'].replace('_', ' ').title()}")
    if p.get("mls_number"):
        parts.append(f"MLS#: {p['mls_number']}")
    if p.get("features"):
        features = p["features"] if isinstance(p["features"], list) else []
        if features:
            parts.append(f"Features: {', '.join(features)}")
    if p.get("description"):
        parts.append(f"Description: {p['description']}")
    return "\n".join(parts)
