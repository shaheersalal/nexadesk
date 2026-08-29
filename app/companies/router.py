from fastapi import APIRouter, HTTPException, status, Depends

from app.auth.middleware import CurrentUser, CompanyId, AccessibleCompanyIds
from app.auth.middleware import require_owner_or_admin
from app.config import get_settings
from app.dependencies import RlsDb, get_supabase_admin
from app.companies.models import CompanyUpdate, ChildCompanyCreate

router = APIRouter()


@router.patch("/me")
async def update_my_company(body: CompanyUpdate, company_id: CompanyId, current_user: CurrentUser):
    # Service-role on purpose: `companies` carries a SELECT policy only, so an
    # UPDATE as the caller is refused by the database. Adding write policies is
    # the proper fix and needs a migration; until then the company_id filter
    # below is the boundary, and it comes from the verified session rather than
    # from the request.
    payload = body.model_dump(exclude_unset=True)
    sb = get_supabase_admin()
    result = sb.table("companies").update(payload).eq("id", company_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")
    return result.data[0]


@router.get("/accessible")
async def list_accessible_companies(
    db: RlsDb,
    company_id: CompanyId,
    accessible_company_ids: AccessibleCompanyIds,
    current_user: CurrentUser,
):
    """Return company rows for all IDs the current user can access (self + children)."""
    sb = db
    result = (
        sb.table("companies")
        .select("id, name, parent_company_id")
        .in_("id", accessible_company_ids)
        .order("name")
        .execute()
    )
    return result.data


@router.post("/child", status_code=status.HTTP_201_CREATED)
# Service-role: creating a company means writing a row the caller cannot yet be
# scoped to, and `companies` has no INSERT policy. The parent relationship is
# validated in code.
async def create_child_company(
    body: ChildCompanyCreate,
    company_id: CompanyId,
    current_user: CurrentUser,
    _auth: dict = Depends(require_owner_or_admin),
):
    """
    Create a child company under the caller's company and invite a user into it.
    Restricted to owner/admin of the parent company (not available to child accounts
    themselves — you can't create grandchildren).
    """
    sb = get_supabase_admin()
    settings = get_settings()

    # Verify the caller's own company is NOT already a child (enforce one-level nesting
    # on the API side as well — the DB trigger enforces it too, but fail fast with a
    # clear error message rather than letting the DB trigger surface it as a 500).
    caller_company = sb.table("companies").select("parent_company_id").eq("id", company_id).single().execute()
    if caller_company.data and caller_company.data.get("parent_company_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Child accounts cannot create their own child companies (one level of nesting only).",
        )

    # Create the child company row first (so we have its id for the invite metadata)
    child = (
        sb.table("companies")
        .insert({"name": body.name.strip(), "parent_company_id": company_id})
        .execute()
    )
    child_company_id = child.data[0]["id"]

    # Invite the user; handle_new_user() will see child_company_id in
    # raw_user_meta_data and link them to this company instead of creating a new one.
    try:
        meta = {"child_company_id": child_company_id}
        if body.full_name:
            meta["full_name"] = body.full_name
        sb.auth.admin.invite_user_by_email(
            body.invite_email,
            options={
                "data": meta,
                "redirect_to": f"{settings.FRONTEND_URL}/setup" if hasattr(settings, "FRONTEND_URL") else "https://nexadesk.site/setup",
            },
        )
    except Exception as e:
        # If the invite fails, roll back the company creation so we don't leave
        # an orphan company with no linked user.
        sb.table("companies").delete().eq("id", child_company_id).execute()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Child company created but invite failed: {e}. Company was rolled back.",
        )

    return {
        "id": child_company_id,
        "name": body.name.strip(),
        "parent_company_id": company_id,
        "invite_sent_to": body.invite_email,
    }
