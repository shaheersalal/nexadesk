"""
WS /voice-demo/stream â€” browser push-to-talk voice demo.

Protocol (client â†’ server):
  JSON text  â€” {"type":"lang","lang":"en","mimeType":"audio/webm;codecs=opus"}
               Control frame sent before every audio frame.  Does NOT count
               as a turn. Sets the language and container format for the next
               binary frame.
  Binary     â€” Raw audio (WebM/Opus or whatever MediaRecorder produced).
               Server transcribes with OpenAI whisper-1 using the lang/mime
               received in the preceding control frame.
  JSON text  â€” {"type":"text_input","text":"..."} â€” future / testing use only.

Protocol (server â†’ client):
  {"type":"status",     "stage":"transcribing"|"thinking"|"speaking"|"idle"}
  {"type":"transcript", "text":"..."}
  {"type":"reply_text", "text":"..."}
  {"type":"error",      "message":"..."}
  Binary  â€” MP3 audio chunk (one per sentence, streamed sentence-by-sentence)

Debug: set env VOICE_DEMO_DEBUG=1 to save each received WebM to
  /tmp/voice_demo_debug/<ms-timestamp>.webm and log side-by-side with transcript.
"""
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.shared import llm
from app.shared.demo_prompt import DEMO_KNOWLEDGE_PROMPT
from app.shared.language import anormalize_for_llm
from app.voice_demo.local_stt import transcribe
from app.voice_demo.local_tts import synthesize

router = APIRouter()
logger = logging.getLogger("nexadesk.voice_demo")

MAX_TURNS = 20

# Approximate minimum for a ~1.5 s clip at 128 kbps Opus inside WebM.
# 128 000 bps Ã— 1.5 s / 8 â‰ˆ 24 000 bytes; we use half as a loose server guard
# because browsers may not hit exactly 128 kbps.  The primary guard is the
# 1 500 ms client-side check; this catches only truly empty / corrupt frames.
_MIN_AUDIO_BYTES = 8_000

_VOICE_SYSTEM = (
    DEMO_KNOWLEDGE_PROMPT
    + "\n\nIMPORTANT: This is a voice call. Reply in 1â€“2 short sentences only. No bullet points or lists."
)

_LANG_RESPONSE: dict[str, str] = {
    "ur": "IMPORTANT: You MUST respond ONLY in Urdu (Ø§Ø±Ø¯Ùˆ) using Arabic Nastaliq script. Do NOT write any English words.",
    "ar": "IMPORTANT: You MUST respond ONLY in Arabic (Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©). Do NOT write any English words.",
}

_DEBUG = os.getenv("VOICE_DEMO_DEBUG") == "1"


def _maybe_save_debug(audio_bytes: bytes, label: str) -> None:
    """Save audio to /tmp/voice_demo_debug/ when VOICE_DEMO_DEBUG=1."""
    if not _DEBUG:
        return
    import pathlib
    import time
    d = pathlib.Path("/tmp/voice_demo_debug")
    d.mkdir(parents=True, exist_ok=True)
    ts   = int(time.time() * 1000)
    path = d / f"{ts}_{label}.webm"
    path.write_bytes(audio_bytes)
    logger.info("DEBUG saved %s (%d bytes)", path, len(audio_bytes))


@router.get("/diag")
async def voice_demo_diag():
    """Diagnostic: confirm TTS is reachable."""
    import traceback
    out: dict = {}
    try:
        mp3 = await synthesize("Hello, I can help you find your perfect property today.")
        out["tts_bytes"] = len(mp3)
        out["tts_ok"]    = len(mp3) > 0
    except Exception:
        out["tts_error"] = traceback.format_exc()
    return out


@router.websocket("/stream")
async def voice_demo_stream(websocket: WebSocket):
    await websocket.accept()

    history: list[dict] = []
    turns = 0

    # Per-connection state set by the "lang" control frame that the client
    # sends immediately before each audio binary frame.
    pending_lang: str = "en"
    pending_mime: str = "audio/webm"

    try:
        while True:
            msg = await websocket.receive()

            raw_bytes = msg.get("bytes")
            raw_text  = msg.get("text")

            # â”€â”€ Control frames (do NOT count as a turn) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if raw_text:
                try:
                    data = json.loads(raw_text)
                except Exception:
                    continue

                if data.get("type") == "lang":
                    # Language + container-format hint for the next audio frame
                    pending_lang = data.get("lang", "en") or "en"
                    pending_mime = data.get("mimeType", "audio/webm") or "audio/webm"
                    logger.debug("lang frame: lang=%s mime=%s", pending_lang, pending_mime)
                    continue

                elif data.get("type") == "text_input":
                    # Pre-transcribed text (testing / future use)
                    transcript = data.get("text", "").strip()
                    if not transcript:
                        continue
                    # Falls through to LLM section below
                else:
                    continue

            elif raw_bytes:
                # Audio frame â€” counts as a turn
                turns += 1
                if turns > MAX_TURNS:
                    await websocket.send_json({
                        "type": "error",
                        "message": "That's the demo limit â€” reach out on Upwork or LinkedIn to keep going.",
                    })
                    break

                n_bytes = len(raw_bytes)
                approx_dur = n_bytes / 16_000   # rough: 128 kbps = 16 000 B/s

                if n_bytes < _MIN_AUDIO_BYTES:
                    logger.warning(
                        "audio too short: %d bytes (~%.2fs) â€” skipping STT",
                        n_bytes, approx_dur,
                    )
                    await websocket.send_json({
                        "type": "error",
                        "message": "Didn't catch that â€” hold the button a bit longer.",
                    })
                    continue

                _maybe_save_debug(raw_bytes, f"turn{turns}")

                await websocket.send_json({"type": "status", "stage": "transcribing"})
                try:
                    transcript = await transcribe(
                        raw_bytes,
                        language=pending_lang,
                        mime_type=pending_mime,
                    )
                except Exception as e:
                    logger.error("STT exception turn=%d: %s", turns, e)
                    await websocket.send_json({"type": "error", "message": f"STT error: {e}"})
                    continue

                logger.info(
                    "STT turn=%d  bytes=%d  ~%.1fs  lang=%s  â†’ %r",
                    turns, n_bytes, approx_dur, pending_lang, transcript,
                )

            else:
                continue

            # â”€â”€ Common: validate transcript â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if not transcript.strip():
                await websocket.send_json({
                    "type": "error",
                    "message": "Didn't catch that â€” try again?",
                })
                continue

            await websocket.send_json({"type": "transcript", "text": transcript})
            await websocket.send_json({"type": "status", "stage": "thinking"})

            # User's explicit language selection is ground truth.
            # Pass the transcript directly â€” gpt-4o-mini understands all languages.
            if pending_lang and pending_lang != "auto":
                detected_lang = pending_lang
                llm_query = transcript
            else:
                llm_query, detected_lang = await anormalize_for_llm(transcript)

            lang_note = _LANG_RESPONSE.get(detected_lang, "")
            voice_system = _VOICE_SYSTEM + (f"\n\n{lang_note}" if lang_note else "")

            history.append({"role": "user", "content": llm_query})

            # â”€â”€ LLM â†’ collect full reply â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            reply_parts: list[str] = []
            try:
                history_for_llm = history[:-1][-10:] + [{"role": "user", "content": llm_query}]
                async for chunk in llm.stream(
                    system=voice_system,
                    messages=history_for_llm,
                    max_tokens=150,
                ):
                    reply_parts.append(chunk)
            except Exception as e:
                logger.error("LLM stream error: %s", e)

            reply = "".join(reply_parts).strip()
            logger.info("LLM reply  lang=%s  â†’ %r", detected_lang, reply[:120])

            if not reply:
                history.pop()
                await websocket.send_json({"type": "status", "stage": "idle"})
                continue

            history.append({"role": "assistant", "content": reply})
            await websocket.send_json({"type": "reply_text", "text": reply})

            # â”€â”€ TTS â€” full reply as one call â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Sentence-by-sentence splitting caused broken fragments when prices
            # contained decimal points (e.g. "AED 2.5M." split into "AED 2." + "5M.").
            try:
                await websocket.send_json({"type": "status", "stage": "speaking"})
                audio = await synthesize(reply, detected_lang)
                if audio:
                    await websocket.send_bytes(audio)
            except Exception as e:
                logger.error("TTS error: %s", e)

            await websocket.send_json({"type": "status", "stage": "idle"})

    except WebSocketDisconnect:
        pass
