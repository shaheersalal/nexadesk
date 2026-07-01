"""
Resolves the set of company IDs the current authenticated user may read from.

For a top-level (parent) account: returns own company_id plus all direct
children's company_ids. For a child or normal single-company account: returns
only own company_id. Backed by the `accessible_company_ids()` Postgres function
added in migrations/0002_parent_child_companies.sql.

Used as a FastAPI dependency via AccessibleCompanyIds in app/auth/middleware.py.
"""
from typing import Annotated
from fastapi import Depends

from app.dependencies import get_supabase_admin, get_company_id
from app.dependencies import get_current_user


async def get_accessible_company_ids(
    company_id: Annotated[str, Depends(get_company_id)],
) -> list[str]:
    """Return [company_id] for a normal/child user, [company_id, *child_ids] for a parent."""
    sb = get_supabase_admin()
    result = (
        sb.table("companies")
        .select("id")
        .eq("parent_company_id", company_id)
        .execute()
    )
    child_ids = [r["id"] for r in (result.data or [])]
    return [company_id] + child_ids
