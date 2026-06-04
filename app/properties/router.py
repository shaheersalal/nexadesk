from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from app.auth.middleware import CurrentUser, CompanyId
from app.dependencies import get_supabase_admin
from app.properties.models import PropertyCreate, PropertyUpdate, property_to_text

router = APIRouter()


def _supabase():
    return get_supabase_admin()


@router.get("/")
async def list_properties(company_id: CompanyId):
    sb = _supabase()
    result = sb.table("properties").select("*").eq("company_id", company_id).order("created_at", desc=True).execute()
    return result.data


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_property(
    body: PropertyCreate,
    company_id: CompanyId,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    sb = _supabase()
    row = body.model_dump()
    row["company_id"] = company_id
    # Convert Decimal → float for JSON serialisation
    if row.get("price") is not None:
        row["price"] = float(row["price"])

    result = sb.table("properties").insert(row).execute()
    property_data = result.data[0]

    # Auto-ingest into RAG in background
    background_tasks.add_task(_auto_ingest_property, property_data, company_id)

    return property_data


@router.get("/{property_id}")
async def get_property(property_id: UUID, company_id: CompanyId):
    sb = _supabase()
    result = (
        sb.table("properties")
        .select("*")
        .eq("id", str(property_id))
        .eq("company_id", company_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Property not found")
    return result.data


@router.patch("/{property_id}")
async def update_property(
    property_id: UUID,
    body: PropertyUpdate,
    company_id: CompanyId,
    background_tasks: BackgroundTasks,
):
    sb = _supabase()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "price" in updates and updates["price"] is not None:
        updates["price"] = float(updates["price"])

    result = (
        sb.table("properties")
        .update(updates)
        .eq("id", str(property_id))
        .eq("company_id", company_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Property not found")

    background_tasks.add_task(_auto_ingest_property, result.data[0], company_id)
    return result.data[0]


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(property_id: UUID, company_id: CompanyId):
    sb = _supabase()
    sb.table("properties").delete().eq("id", str(property_id)).eq("company_id", company_id).execute()


async def _auto_ingest_property(property_data: dict, company_id: str):
    """Auto-generate a text summary of the property and ingest into Qdrant."""
    from app.rag.pipeline import ingest_text
    text = property_to_text(property_data)
    await ingest_text(
        text=text,
        company_id=company_id,
        metadata={
            "source_type": "property_form",
            "property_id": property_data["id"],
            "doc_category": "listing",
            "filename": f"property_{property_data['id']}.txt",
        },
    )
