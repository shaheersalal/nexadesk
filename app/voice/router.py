"""
Voice routes:
  POST /voice/inbound  — Twilio webhook (call arrives, return TwiML)
  POST /voice/status   — Twilio call status webhook (call ended)
  WS   /voice/stream/{call_sid} — Twilio Media Streams WebSocket
"""
import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import Response

from app.config import get_settings
from app.dependencies import get_redis, get_supabase_admin
from app.voice.telephony import build_stream_twiml, build_fallback_twiml
from app.voice.call_session import create_session, load_session, save_session, delete_session
from app.voice.stt import transcribe_mulaw_b64
from app.voice.tts import synthesize_to_mulaw
from app.voice.conversation import process_voice_turn
from app.shared.llm import complete as llm_complete
from app.shared.prompts import CALL_GREETING, LEAD_SUMMARY_PROMPT

router = APIRouter()
settings = get_settings()

# Buffer to accumulate audio before transcribing (avoid transcribing tiny chunks)
AUDIO_BUFFER_CHUNKS = 8  # ~1 second of 8kHz mulaw


def _validate_twilio(request: Request, form: dict) -> bool:
    """Return True if Twilio signature is valid (or Twilio is not configured)."""
    if not settings.TELEPHONY_AUTH_TOKEN:
        return True  # Dev mode — no Twilio configured
    from app.voice.telephony import validate_twilio_signature
    sig = request.headers.get("X-Twilio-Signature", "")
    return validate_twilio_signature(str(request.url), dict(form), sig)


@router.post("/inbound")
async def inbound_call(request: Request):
    """Twilio calls this when someone dials our number. Return TwiML to start stream."""
    from fastapi import HTTPException
    form = await request.form()
    if not _validate_twilio(request, form):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    call_sid = form.get("CallSid", "unknown")

    # Resolve company_id from the called phone number
    company_id = await _resolve_company_id(form.get("To", ""))
    if not company_id:
        twiml = build_fallback_twiml(
            "Thank you for calling. We are unavailable right now. Please try again later."
        )
        return Response(content=twiml, media_type="application/xml")

    # Create Redis session
    redis = await get_redis(settings)
    session = await create_session(call_sid, company_id, redis)

    twiml = build_stream_twiml(call_sid)
    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def call_status(request: Request):
    """Twilio status webhook — called when call ends."""
    from fastapi import HTTPException
    form = await request.form()
    if not _validate_twilio(request, form):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    duration = form.get("CallDuration", 0)

    if call_status in ("completed", "failed", "busy", "no-answer"):
        redis = await get_redis(settings)
        session = await load_session(call_sid, redis)
        if session:
            await _finalize_call(session, int(duration))
            await delete_session(call_sid, redis)

    return Response(content="", status_code=204)


@router.websocket("/stream/{call_sid}")
async def media_stream(websocket: WebSocket, call_sid: str):
    """
    Twilio Media Streams WebSocket.
    Receives audio events, accumulates chunks, transcribes, gets LLM reply, sends TTS back.
    """
    await websocket.accept()
    redis = await get_redis(settings)
    session = await load_session(call_sid, redis)

    if not session:
        await websocket.close()
        return

    # Send greeting immediately
    company_name = await _get_company_name(session.company_id)
    greeting = CALL_GREETING.format(company_name=company_name, ai_name=settings.APP_NAME)
    await _send_tts(websocket, greeting, call_sid)

    audio_buffer: list[str] = []  # base64 encoded mulaw chunks

    try:
        while True:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            msg = json.loads(raw)
            event_type = msg.get("event")

            if event_type == "media":
                audio_b64 = msg["media"]["payload"]
                audio_buffer.append(audio_b64)

                # Transcribe when buffer is large enough
                if len(audio_buffer) >= AUDIO_BUFFER_CHUNKS:
                    combined_b64 = _combine_audio_chunks(audio_buffer)
                    audio_buffer = []

                    transcript = await transcribe_mulaw_b64(combined_b64, session.language)
                    if transcript.strip():
                        reply, _ = await process_voice_turn(transcript, session)
                        await save_session(session, redis)
                        await _send_tts(websocket, reply, call_sid)

            elif event_type == "stop":
                break

    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        # Transcribe any remaining buffer
        if audio_buffer:
            combined = _combine_audio_chunks(audio_buffer)
            leftover = await transcribe_mulaw_b64(combined, session.language)
            if leftover.strip():
                await process_voice_turn(leftover, session)
        await save_session(session, redis)


async def _send_tts(websocket: WebSocket, text: str, call_sid: str) -> None:
    """Synthesize text and send back to Twilio over the media stream."""
    import base64
    audio_bytes = await synthesize_to_mulaw(text)
    if audio_bytes:
        msg = {
            "event": "media",
            "streamSid": call_sid,
            "media": {"payload": base64.b64encode(audio_bytes).decode()},
        }
        await websocket.send_text(json.dumps(msg))
    else:
        # Fallback: send a mark event so Twilio uses <Say> (handled in TwiML)
        pass


async def _finalize_call(session, duration: int) -> None:
    """After call ends: create/update lead + save conversation."""
    sb = get_supabase_admin()

    # Generate a summary of lead_data using LLM
    if session.transcript_parts:
        transcript_text = "\n".join(session.transcript_parts)
        summary_json = await llm_complete(
            system="You extract lead information from call transcripts. Return only valid JSON.",
            messages=[{"role": "user", "content": LEAD_SUMMARY_PROMPT.format(transcript=transcript_text)}],
            max_tokens=400,
            temperature=0.0,
        )
        try:
            import json as json_mod
            extracted = json_mod.loads(summary_json)
        except Exception:
            extracted = {}
    else:
        extracted = {}
        transcript_text = ""

    # Merge extracted data with what session already captured
    lead_data = {**extracted, **{k: v for k, v in session.lead_data.items() if v}}

    # Upsert lead
    lead_payload = {
        "company_id": session.company_id,
        "source": "voice",
        "status": "new",
        "score": session.score,
        "language": session.language,
        "notes": lead_data.get("notes", ""),
    }
    for field in ("name", "phone", "email"):
        if lead_data.get(field):
            lead_payload[field] = lead_data[field]

    if session.lead_id:
        sb.table("leads").update(lead_payload).eq("id", session.lead_id).execute()
        lead_id = session.lead_id
    else:
        lead_result = sb.table("leads").insert(lead_payload).execute()
        lead_id = lead_result.data[0]["id"] if lead_result.data else None

    # Save conversation
    if transcript_text and lead_id:
        turns = []
        for part in session.transcript_parts:
            if part.startswith("Caller: "):
                turns.append({"role": "user", "content": part[8:], "timestamp": session.started_at})
            elif part.startswith("AI: "):
                turns.append({"role": "assistant", "content": part[4:], "timestamp": session.started_at})

        sb.table("conversations").insert({
            "company_id": session.company_id,
            "lead_id": lead_id,
            "channel": "voice",
            "session_id": session.call_sid,
            "transcript": turns,
            "summary": lead_data.get("notes", ""),
            "language": session.language,
            "call_duration": duration,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }).execute()


async def _resolve_company_id(phone_number: str) -> str | None:
    """Look up company by their Twilio phone number."""
    sb = get_supabase_admin()
    result = sb.table("companies").select("id").eq("phone", phone_number).execute()
    if result.data:
        return result.data[0]["id"]
    # Fallback: return first company (for single-tenant demo)
    result = sb.table("companies").select("id").limit(1).execute()
    return result.data[0]["id"] if result.data else None


async def _get_company_name(company_id: str) -> str:
    sb = get_supabase_admin()
    result = sb.table("companies").select("name").eq("id", company_id).single().execute()
    return (result.data or {}).get("name", settings.APP_NAME)


def _combine_audio_chunks(chunks: list[str]) -> str:
    """Concatenate base64 encoded mulaw chunks into one."""
    import base64
    combined = b"".join(base64.b64decode(c) for c in chunks)
    return base64.b64encode(combined).decode()
