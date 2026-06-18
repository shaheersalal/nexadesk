"""
Google Calendar integration for appointment booking.
OAuth2 flow: the realtor authorises once, tokens stored in Supabase.
"""
import json
from typing import Optional
from datetime import datetime, timedelta

from app.config import get_settings
from app.dependencies import get_supabase_admin

settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_oauth_flow():
    from google_auth_oauthlib.flow import Flow
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
                "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.calendar_redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.calendar_redirect_uri,
    )


def get_auth_url() -> str:
    flow = get_oauth_flow()
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return auth_url


async def exchange_code(code: str, company_id: str) -> bool:
    """Exchange OAuth code for tokens and store in Supabase."""
    try:
        flow = get_oauth_flow()
        flow.fetch_token(code=code)
        creds = flow.credentials
        tokens = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or []),
        }
        sb = get_supabase_admin()
        sb.table("companies").update({"calendar_tokens": json.dumps(tokens)}).eq("id", company_id).execute()
        return True
    except Exception:
        return False


def _get_service(tokens_json: str):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    tokens = json.loads(tokens_json)
    creds = Credentials(
        token=tokens["token"],
        refresh_token=tokens.get("refresh_token"),
        token_uri=tokens["token_uri"],
        client_id=tokens["client_id"],
        client_secret=tokens["client_secret"],
        scopes=tokens.get("scopes"),
    )
    return build("calendar", "v3", credentials=creds)


async def create_event(
    company_id: str,
    summary: str,
    start_dt: datetime,
    duration_minutes: int = 30,
    description: str = "",
    attendee_email: Optional[str] = None,
) -> Optional[str]:
    """
    Create a Google Calendar event. Returns the Google event ID or None.
    """
    if not settings.GOOGLE_CALENDAR_CLIENT_ID:
        return None

    sb = get_supabase_admin()
    company = sb.table("companies").select("calendar_tokens").eq("id", company_id).single().execute()
    tokens_json = (company.data or {}).get("calendar_tokens")
    if not tokens_json:
        return None

    try:
        service = _get_service(tokens_json)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
        }
        if attendee_email:
            event_body["attendees"] = [{"email": attendee_email}]

        event = service.events().insert(calendarId="primary", body=event_body).execute()
        return event.get("id")
    except Exception:
        return None


async def delete_event(company_id: str, google_event_id: str) -> bool:
    sb = get_supabase_admin()
    company = sb.table("companies").select("calendar_tokens").eq("id", company_id).single().execute()
    tokens_json = (company.data or {}).get("calendar_tokens")
    if not tokens_json:
        return False
    try:
        service = _get_service(tokens_json)
        service.events().delete(calendarId="primary", eventId=google_event_id).execute()
        return True
    except Exception:
        return False
