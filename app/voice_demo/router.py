"""
WS /voice-demo/stream — browser push-to-talk voice demo (embeddable on
nexadesk.site and shaheer.dev).

Push-to-talk, not continuous streaming: the client records one full turn with
MediaRecorder and sends the finished blob as a single binary WS frame. Each
turn is: faster-whisper STT -> orchestrator (RAG-grounded reply) -> Kokoro TTS
-> binary MP3 frame back to the browser.

Both STT and TTS are fully self-hosted (no API key needed).
"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.orchestrator import run as orchestrator_run
from app.shared.demo_company import resolve_demo_company
from app.voice_demo.local_stt import transcribe
from app.voice_demo.local_tts import synthesize

router = APIRouter()
logger = logging.getLogger("nexadesk.voice_demo")

MAX_TURNS = 20


@router.websocket("/stream")
async def voice_demo_stream(websocket: WebSocket):
    await websocket.accept()

    company = await resolve_demo_company()
    if not company:
        await websocket.send_json({
            "type": "error",
            "message": "Demo is warming up — try again in a moment.",
        })
        await websocket.close()
        return

    history: list[dict] = []
    lead_id = None
    turns = 0

    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            turns += 1
            if turns > MAX_TURNS:
                await websocket.send_json({
                    "type": "error",
                    "message": "That's the demo limit for this session — reach out on Upwork or LinkedIn to keep going.",
                })
                break

            await websocket.send_json({"type": "status", "stage": "transcribing"})
            try:
                transcript = await transcribe(audio_bytes)
            except Exception as e:
                logger.error("Voice demo STT failed: %s", e)
                await websocket.send_json({
                    "type": "error",
                    "message": "Transcription failed — try again.",
                })
                continue

            if not transcript.strip():
                await websocket.send_json({"type": "error", "message": "Didn't catch that — try again?"})
                continue

            await websocket.send_json({"type": "transcript", "text": transcript})
            await websocket.send_json({"type": "status", "stage": "thinking"})

            history.append({"role": "user", "content": transcript})
            try:
                result = await orchestrator_run(
                    user_message=transcript,
                    company_id=company["id"],
                    history=history[-10:],
                    company=company,
                    lead_id=lead_id,
                )
            except Exception as e:
                logger.error("Voice demo orchestrator failed: %s", e)
                await websocket.send_json({
                    "type": "error",
                    "message": "Demo is warming up — try again in a moment.",
                })
                history.pop()
                continue

            reply = result["reply"]
            lead_id = result["lead_id"]
            history.append({"role": "assistant", "content": result["reply_english"]})

            await websocket.send_json({"type": "reply_text", "text": reply})
            await websocket.send_json({"type": "status", "stage": "speaking"})

            try:
                audio_reply = await synthesize(reply)
            except Exception as e:
                logger.error("Voice demo TTS failed: %s", e)
                await websocket.send_json({
                    "type": "error",
                    "message": "Got a reply but couldn't voice it — see the text above.",
                })
                await websocket.send_json({"type": "status", "stage": "idle"})
                continue

            await websocket.send_bytes(audio_reply)
            await websocket.send_json({"type": "status", "stage": "idle"})

    except WebSocketDisconnect:
        pass
