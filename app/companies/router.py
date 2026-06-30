from fastapi import APIRouter

from app.auth.middleware import CurrentUser, CompanyId
from app.dependencies import get_supabase_admin
from app.companies.models import CompanyUpdate

router = APIRouter()


@router.patch("/me")
async def update_my_company(body: CompanyUpdate, company_id: CompanyId, current_user: CurrentUser):
    payload = body.model_dump(exclude_unset=True)
    sb = get_supabase_admin()
    result = sb.table("companies").update(payload).eq("id", company_id).execute()
    return result.data[0]
