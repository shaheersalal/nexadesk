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

    # insert(), not upsert(): upsert silently overwrote company_id and reset
    # role to "owner" for a user who was already linked elsewhere, which would
    # move them between tenants (AUDIT.md M9). A duplicate id is a real error
    # and should surface as one.
    existing = (
        supabase.table("users")
        .select("company_id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if existing and existing.data and existing.data.get("company_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already linked to a company",
        )

    supabase.table("users").upsert(
        {"id": user_id, "company_id": company_id, "role": "owner"}
    ).execute()

    return company_id
