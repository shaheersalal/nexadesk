from fastapi import APIRouter
from pydantic import BaseModel
import httpx

from app.config import get_settings
from app.dependencies import get_supabase_admin

router = APIRouter()


class DemoRequest(BaseModel):
    name: str
    email: str
    agency: str
    phone: str


@router.post("/book-demo")
async def book_demo(body: DemoRequest):
    settings = get_settings()

    # Persist to Supabase (best-effort — table may not exist yet)
    try:
        sb = get_supabase_admin()
        sb.table("demo_requests").insert({
            "name": body.name,
            "email": body.email,
            "agency_name": body.agency,
            "phone": body.phone,
        }).execute()
    except Exception:
        pass

    # Notify via Resend
    if settings.RESEND_API_KEY:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": "NexaDesk <onboarding@resend.dev>",
                    "to": ["shaheersalal@gmail.com"],
                    "subject": f"New Demo Request — {body.agency}",
                    "html": f"""
<div style="font-family:sans-serif;max-width:520px;color:#1a1a1a">
  <h2 style="color:#1e3a5f;margin-bottom:20px">New Demo Request 🎯</h2>
  <table style="width:100%;border-collapse:collapse;font-size:15px">
    <tr><td style="padding:10px 0;color:#666;width:130px">Name</td>
        <td style="padding:10px 0;font-weight:600">{body.name}</td></tr>
    <tr style="background:#f9f9f9"><td style="padding:10px 0;color:#666">Email</td>
        <td style="padding:10px 0"><a href="mailto:{body.email}" style="color:#2563eb">{body.email}</a></td></tr>
    <tr><td style="padding:10px 0;color:#666">Agency</td>
        <td style="padding:10px 0;font-weight:600">{body.agency}</td></tr>
    <tr style="background:#f9f9f9"><td style="padding:10px 0;color:#666">Phone</td>
        <td style="padding:10px 0"><a href="tel:{body.phone}" style="color:#2563eb">{body.phone}</a></td></tr>
  </table>
  <p style="margin-top:24px;color:#888;font-size:13px">Sent from nexadesk.site landing page</p>
</div>
                    """,
                },
            )

    return {"status": "ok"}
