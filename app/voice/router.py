"""
Voice routes:
  POST /voice/inbound  — Twilio webhook (call arrives, return TwiML)
  POST /voice/status   — Twilio call status webhook (call ended)
  WS   /voice/stream/{call_sid} — Twilio Media Streams WebSocket
"""
import asyncio
import base64
import hashlib
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import Response

from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.dependencies import get_redis, get_supabase_admin
from app.voice.telephony import build_stream_twiml, build_fallback_twiml, twilio_client
from app.voice.call_session import create_session, load_session, save_session, delete_session
from app.voice.stt_stream import DeepgramStream
from app.voice.turn_taking import SpokenLog, collect_turn
from app.voice.tts import synthesize_to_mulaw
from app.voice.tts_live import speak_tokens
from app.voice.conversation import stream_voice_turn
from app.shared.llm import complete as llm_complete
from app.shared.prompts import CALL_GREETING, CALL_GREETING_NO_STOCK, LEAD_SUMMARY_PROMPT

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("nexadesk.voice")


def _validate_twilio(request: Request, form: dict) -> bool:
    """
    Return True if the Twilio signature is valid.

    When TELEPHONY_AUTH_TOKEN is unset this returns True so local development
    works without Twilio credentials. That is only safe because startup now
    refuses to boot in production without the token (see app/main.py) — without
    that guard this is a silent open door on the voice webhooks (AUDIT.md C3).
    """
    if not settings.TELEPHONY_AUTH_TOKEN:
        if settings.APP_ENV == "production":
            # Belt and braces: should be unreachable, startup already failed.
            logger.error("Refusing to accept unsigned Twilio webhook in production")
            return False
        return True
    from app.voice.telephony import validate_twilio_signature
    sig = request.headers.get("X-Twilio-Signature", "")
    return validate_twilio_signature(_callback_url(request), dict(form), sig)


def _callback_url(request: Request) -> str:
    """
    Rebuild the URL exactly as Twilio saw it when it computed the signature.

    `str(request.url)` is wrong behind Railway. Twilio signs the https:// URL it
    was configured with, but uvicorn only honours X-Forwarded-Proto from
    `--forwarded-allow-ips` (default 127.0.0.1), and Railway's proxy is not on
    loopback — so the app reconstructs http:// and every signature check fails.
    Real inbound calls were rejected 403 and the line never answered.

    Widening `--forwarded-allow-ips` would fix the scheme and simultaneously make
    X-Forwarded-For client-controlled, which is precisely what TRUST_PROXY_HEADERS
    exists to prevent. So the base comes from configuration instead: it is the
    same value the webhook was registered with, which is what Twilio signed, and
    it cannot be influenced by the caller.
    """
    base = (settings.TELEPHONY_WEBHOOK_BASE_URL or "").rstrip("/")
    if not base:
        return str(request.url)
    url = f"{base}{request.url.path}"
    return f"{url}?{request.url.query}" if request.url.query else url


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

    # Create Redis session (side effect: stored under call_sid for the WS to load)
    redis = await get_redis(settings)
    await create_session(call_sid, company_id, redis, caller_number=form.get("From"))

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
    Twilio Media Streams WebSocket — fully streamed pipeline.

    Audio flows continuously into Deepgram's streaming API, which does the voice
    activity detection and tells us when the caller has finished an utterance.
    That utterance drives a streamed LLM response, whose tokens are cut into
    clauses and synthesised as they arrive, so the caller hears the first
    sentence while the model is still writing the rest.

    The previous implementation buffered 8 Twilio frames (160 ms, despite a
    comment claiming ~1 s), POSTed each slice to Deepgram's batch endpoint, then
    waited for the full LLM reply and the full TTS render before sending
    anything (AUDIT.md H2, M1, M2).
    """
    await websocket.accept()
    redis = await get_redis(settings)
    session = await load_session(call_sid, redis)

    if not session:
        await websocket.close()
        return

    # Twilio requires the streamSid from the `start` event on every outbound
    # media frame. Sending call_sid instead meant Twilio silently discarded all
    # our audio and the caller heard nothing (AUDIT.md H2).
    stream_sid: str | None = None
    speaking = asyncio.Lock()
    # What the assistant has said, so it can recognise itself coming back.
    spoken = SpokenLog()

    stt_language = session.language if session.language_confirmed else None

    try:
        async with DeepgramStream(language=stt_language) as stt:

            async def _pump_turns() -> None:
                """Run a turn for each thing the caller actually says."""
                while True:
                    try:
                        utterance = await collect_turn(stt)
                    except asyncio.TimeoutError:
                        logger.info("Caller silent — ending turn pump")
                        return
                    if utterance is None:
                        return
                    if not utterance.strip():
                        continue

                    # Attribution: the line echoes, and Deepgram cannot tell our
                    # voice from theirs. Without this the assistant answers its
                    # own last sentence, which is the single most damning thing
                    # a demo can do.
                    score = spoken.echo_score(utterance)
                    if score >= 0.62:
                        spoken.suppressed += 1
                        logger.info("Ignored own speech (echo %.2f): %s", score, utterance)
                        continue

                    logger.info("Caller (%s): %s", call_sid, utterance)
                    # Serialise turns: overlapping replies would interleave audio.
                    async with speaking:
                        await _speak_stream(
                            websocket,
                            stream_sid,
                            _record_spoken(stream_voice_turn(utterance, session), spoken),
                            stt=stt,
                            spoken=spoken,
                        )
                    await save_session(session, redis)

            async def _greet(sid: str | None) -> None:
                try:
                    greeting = await _build_greeting(session.company_id)
                    spoken.note_spoken(greeting)
                    async with speaking:
                        await _speak_greeting(websocket, sid, greeting, redis, spoken)
                except Exception as exc:
                    logger.error("Greeting failed for %s: %s", call_sid, exc, exc_info=True)

            greet_task: asyncio.Task | None = None
            turn_task = asyncio.create_task(_pump_turns())

            try:
                while True:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    msg = json.loads(raw)
                    event_type = msg.get("event")

                    if event_type == "start":
                        stream_sid = msg.get("start", {}).get("streamSid") or msg.get("streamSid")
                        logger.info("Media stream started: call=%s stream=%s", call_sid, stream_sid)
                        # Greet in a task, not inline. Building the greeting hits
                        # the database and then the TTS socket, and awaiting that
                        # here stops this loop reading media frames — so every
                        # word the caller says while being greeted sat in the
                        # socket buffer and arrived afterwards in one burst.
                        greet_task = asyncio.create_task(_greet(stream_sid))

                    elif event_type == "media":
                        frame = base64.b64decode(msg["media"]["payload"])
                        # Feed the frame to our own voice activity tracking as
                        # well: the turn is only over when the transcript has
                        # settled *and* the caller has actually stopped talking.
                        stt.note_audio(frame)
                        await stt.send(frame)

                    elif event_type == "stop":
                        break

            finally:
                if greet_task:
                    greet_task.cancel()
                await stt.close()
                # Let any in-flight turn finish writing to the session.
                try:
                    await asyncio.wait_for(turn_task, timeout=10.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    turn_task.cancel()

    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as exc:
        logger.error("Media stream error for %s: %s", call_sid, exc, exc_info=True)
    finally:
        await save_session(session, redis)


async def _record_spoken(tokens, spoken: SpokenLog):
    """Tee the reply's tokens into the spoken log on their way to synthesis."""
    async for token in tokens:
        if token:
            spoken.note_spoken(token)
        yield token


def _caller_is_interrupting(stt, spoken: SpokenLog | None) -> bool:
    """
    Is somebody talking over us, or are we hearing ourselves?

    Deepgram's voice activity flag cannot tell the difference — an echo of the
    assistant trips it exactly like a person does — and acting on the flag
    alone means the assistant stops dead two words into its own sentence for no
    reason anyone on the call can see.

    So while we are speaking, an interruption has to be backed by words, and
    the words have to not be ours. That costs the time it takes Deepgram to
    produce an interim, which is roughly how long a person waits before
    yielding anyway.
    """
    if stt is None or not stt.speech_started.is_set():
        return False
    if spoken is None:
        return True                      # nothing to compare against
    heard = stt.live_text()
    if not heard:
        return False                     # voice activity with no words yet
    return not spoken.is_echo(heard)


async def _speak_stream(
    websocket: WebSocket,
    stream_sid: str | None,
    token_iter,
    stt=None,
    spoken: SpokenLog | None = None,
) -> None:
    """
    Speak a streamed reply, and stop the moment the caller talks over it.

    Audio comes from one continuous synthesis socket rather than a synthesis
    request per clause, so there is no seam between fragments and no gap when a
    fragment loses its race with playback.

    Barge-in: if Deepgram's VAD reports speech while we are talking, we stop
    sending and tell Twilio to drop whatever is already queued. Without the
    clear, Twilio keeps playing seconds of buffered audio the caller is
    talking over, which is the behaviour people hate most in phone bots.
    """
    if not stream_sid:
        logger.error("No streamSid yet — dropping reply audio")
        return

    if stt is not None:
        stt.speech_started.clear()

    started = time.monotonic()
    interrupted = False
    async for audio in speak_tokens(token_iter):
        if (time.monotonic() - started > BARGE_IN_GRACE
                and _caller_is_interrupting(stt, spoken)):
            interrupted = True
            break
        if spoken is not None:
            spoken.mark_audio_sent()
        await _send_media(websocket, stream_sid, audio)

    if interrupted:
        logger.info("Caller barged in — clearing queued audio")
        try:
            await websocket.send_text(json.dumps({
                "event": "clear", "streamSid": stream_sid,
            }))
        except Exception:
            pass


async def _send_media(websocket: WebSocket, stream_sid: str, audio: bytes) -> None:
    """Send one mulaw payload to Twilio on the active stream."""
    await websocket.send_text(json.dumps({
        "event": "media",
        "streamSid": stream_sid,
        "media": {"payload": base64.b64encode(audio).decode()},
    }))


# Deepgram's VAD can report speech in the moment right after the caller's own
# turn ends — the tail of what they just said, a breath, line noise. Without a
# grace window that reads as a barge-in the instant the reply starts, so the
# assistant says two words and stops dead, which is worse than not stopping.
BARGE_IN_GRACE = 0.5


GREETING_CACHE_TTL = 60 * 60 * 24  # a day; the key changes if the text does




async def _build_greeting(company_id: str) -> str:
    """
    Compose the opening line from the company's own record and inventory.

    Built rather than hardcoded so it stays true per tenant: the name comes from
    the company, and the places come from the listings actually loaded, so it
    can never offer to discuss stock that is not there. A company with no
    listings gets the shorter line instead.
    """
    def _fetch():
        sb = get_supabase_admin()
        company = (
            sb.table("companies")
            .select("name, receptionist_name")
            .eq("id", company_id).maybe_single().execute()
        )
        cities = (
            sb.table("properties").select("city")
            .eq("company_id", company_id).limit(200).execute()
        )
        return company, cities

    try:
        company_res, cities_res = await run_in_threadpool(_fetch)
    except Exception as exc:
        logger.warning("Greeting build failed (%s) — using a plain opener", exc)
        return "Hi, thanks for calling. How can I help?"

    company = (company_res.data if company_res else None) or {}
    ai_name = company.get("receptionist_name") or settings.APP_NAME
    counts: dict[str, int] = {}
    for row in (cities_res.data or []):
        city = (row.get("city") or "").strip()
        if city:
            counts[city] = counts.get(city, 0) + 1
    top = [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:3]]

    if not top:
        return CALL_GREETING_NO_STOCK.format(ai_name=ai_name).strip()

    places = top[0] if len(top) == 1 else ", ".join(top[:-1]) + f" and {top[-1]}"
    return CALL_GREETING.format(ai_name=ai_name, places=places).strip()


async def _speak_greeting(websocket, stream_sid, text: str, redis,
                          spoken: SpokenLog | None = None) -> None:
    """
    Say the greeting, fast on every call including the first.

    A cache hit replays the rendered audio immediately. A miss streams it
    instead of waiting for the whole render: the caller hears the opening words
    in about a second rather than sitting through the full synthesis, and the
    audio is stored on the way past so the next call is instant.

    Rendering the whole greeting up front cost 9 seconds of silence the first
    time a company's greeting changed — which is exactly when a real caller is
    most likely to be on the line, since the text only changes when someone has
    just edited it.
    """
    key = "greeting_mulaw:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    try:
        cached = await redis.get(key)
        if cached:
            if spoken is not None:
                spoken.mark_audio_sent()
            await _send_media(websocket, stream_sid, base64.b64decode(cached))
            return
    except Exception as exc:
        logger.warning("Greeting cache read failed (%s)", exc)

    async def _one() -> "asyncio.AsyncIterator[str]":
        yield text

    collected = bytearray()
    try:
        async for chunk in speak_tokens(_one()):
            collected.extend(chunk)
            if spoken is not None:
                spoken.mark_audio_sent()
            await _send_media(websocket, stream_sid, chunk)
    except Exception as exc:
        logger.error("Greeting synthesis failed: %s", exc)
        await _send_tts(websocket, text, "greeting", stream_sid)
        return

    if collected:
        try:
            await redis.set(key, base64.b64encode(bytes(collected)).decode(),
                            ex=GREETING_CACHE_TTL)
        except Exception:
            pass


async def _send_tts(
    websocket: WebSocket, text: str, call_sid: str, stream_sid: str | None
) -> None:
    """Synthesize text and send back to Twilio over the media stream."""
    audio_bytes = await synthesize_to_mulaw(text)
    if audio_bytes and stream_sid:
        await _send_media(websocket, stream_sid, audio_bytes)
    else:
        # TTS synthesis failed (no API key, ElevenLabs error, or ffmpeg conversion
        # failure) — the Media Stream WS protocol can't inject <Say> mid-stream,
        # so the only way to give the caller audible speech is to redirect the
        # live call out of the stream via the REST API and let Twilio's own
        # <Say> verb speak the fallback TwiML.
        logger.error(f"TTS synthesis returned no audio for call {call_sid}, falling back to Twilio <Say>")
        try:
            twiml = build_fallback_twiml(text)
            twilio_client().calls(call_sid).update(twiml=twiml)
        except Exception as e:
            logger.error(f"Twilio <Say> fallback failed for call {call_sid}: {e}")


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

    # Upsert lead — when updating an existing lead, omit "status" so we don't
    # clobber a status that was already set (e.g. "contacted" after escalation).
    lead_payload = {
        "company_id": session.company_id,
        "score": session.score,
        "language": session.language,
    }
    for field in ("name", "phone", "email"):
        if lead_data.get(field):
            lead_payload[field] = lead_data[field]

    # Caller ID is the fallback phone number. A caller who hangs up before
    # giving details, or who never says a number out loud, still left one on the
    # call — and a lead with no way to reach the person is not a lead. Anything
    # they actually stated wins, since they may be calling from a different
    # phone to the one they want to be reached on.
    if not lead_payload.get("phone") and session.caller_number:
        lead_payload["phone"] = session.caller_number
    if lead_data.get("notes"):
        lead_payload["notes"] = lead_data["notes"]

    if session.lead_id:
        # Defence in depth: the session is already company-scoped, but a forged
        # or stale session id must not be able to write another tenant's lead.
        (
            sb.table("leads").update(lead_payload)
            .eq("id", session.lead_id).eq("company_id", session.company_id).execute()
        )
        lead_id = session.lead_id
    else:
        # New lead — set source and initial status
        lead_payload["source"] = "voice"
        lead_payload["status"] = "new"
        lead_result = sb.table("leads").insert(lead_payload).execute()
        lead_id = lead_result.data[0]["id"] if lead_result.data else None

    # Save conversation.
    #
    # Written for every call that reached this point, not only those with a
    # transcript. A call that connected and produced nothing is still a call the
    # agency needs to see — previously those vanished entirely, leaving an empty
    # lead in the dashboard with no record of where it came from, which is
    # exactly what a missed call looks like and exactly what they most need.
    if lead_id:
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
            "summary": lead_data.get("notes") or (
                "" if transcript_text
                else "Call connected but no conversation took place."
            ),
            "language": session.language,
            "call_duration": duration,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }).execute()


async def _resolve_company_id(phone_number: str) -> str | None:
    """
    Look up the company that owns the dialled number.

    Returns None when nothing matches — the caller then plays the fallback
    TwiML. There is deliberately no "first company" fallback: routing an
    unrecognised number to an arbitrary tenant would read that tenant's
    knowledge base aloud to a stranger and write the resulting lead and full
    transcript into their CRM (AUDIT.md C1).
    """
    if not phone_number:
        return None
    sb = get_supabase_admin()
    result = sb.table("companies").select("id").eq("phone", phone_number).limit(1).execute()
    if result.data:
        return result.data[0]["id"]
    logger.warning(
        "Inbound call to unrecognised number %s — no company owns it, playing fallback",
        phone_number,
    )
    return None


async def _get_company_name(company_id: str) -> str:
    sb = get_supabase_admin()
    result = sb.table("companies").select("name").eq("id", company_id).single().execute()
    return (result.data or {}).get("name", settings.APP_NAME)


