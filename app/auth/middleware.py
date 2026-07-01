"""
Supabase JWT auth helpers. FastAPI dependencies for protected routes.
get_current_user and get_company_id live in app/dependencies.py;
this module adds convenience wrappers and the company-bootstrap flow.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.dependencies import get_current_user, get_supabase_admin, get_company_id
from app.shared.accessible_companies import get_accessible_company_ids

# Re-export for convenience
CurrentUser = Annotated[dict, Depends(get_current_user)]
CompanyId = Annotated[str, Depends(get_company_id)]
AccessibleCompanyIds = Annotated[list[str], Depends(get_accessible_company_ids)]


async def require_owner_or_admin(current_user: CurrentUser) -> dict:
    """Restrict endpoint to owner or admin roles."""
    supabase = get_supabase_admin()
    result = (
        supabase.table("users")
        .select("role")
        .eq("id", current_user["id"])
        .single()
        .execute()
    )
    role = result.data.get("role") if result.data else None
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


async def bootstrap_company(user_id: str, company_name: str, email: str) -> str:
    """
    Called after first Supabase signup. Creates company + links user.
    Returns company_id.
    """
    supabase = get_supabase_admin()

    company = (
        supabase.table("companies")
        .insert({"name": company_name, "email": email})
        .execute()
    )
    company_id = company.data[0]["id"]

    supabase.table("users").upsert(
        {"id": user_id, "company_id": company_id, "role": "owner"}
    ).execute()

    return company_id
