from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.dependencies import get_supabase_admin, get_current_user

ADMIN_UID = "7227a933-56ef-45c4-8cbc-1c8331c74b21"

router = APIRouter()


def require_admin(user=Depends(get_current_user)):
    if user["id"] != ADMIN_UID:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@router.get("/requests")
async def list_requests(_=Depends(require_admin)):
    sb = get_supabase_admin()
    result = sb.table("demo_requests").select("*").order("created_at", desc=True).execute()
    return result.data or []


class InviteBody(BaseModel):
    request_id: str
    email: str
    name: str


@router.post("/invite")
async def invite_user(body: InviteBody, _=Depends(require_admin)):
    sb = get_supabase_admin()
    try:
        sb.auth.admin.invite_user_by_email(
            body.email,
            options={"data": {"full_name": body.name}, "redirect_to": "https://nexadesk.site/setup"},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    sb.table("demo_requests").update({"status": "invited"}).eq("id", body.request_id).execute()
    return {"status": "invited"}
