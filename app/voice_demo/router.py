"""
WS /voice-demo/stream — browser push-to-talk voice demo (embeddable on
nexadesk.site and shaheer.dev).

Push-to-talk, not continuous streaming: the client records one full turn with
MediaRecorder and sends the finished blob as a single binary WS frame. Each
turn is: Whisper STT -> agents/orchestrator.run() (real RAG-grounded reply,
same pipeline as the dashboard chat) -> OpenAI TTS -> binary audio frame back.

Uses EMBED_API_KEY (the genuine OpenAI account key, also used for embeddings)
for Whisper + tts-1, since LLM_API_KEY may point at a non-OpenAI model.
"""
import io
import logging
import uuid

import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.orchestrator import run as orchestrator_run
from app.config import get_settings
from app.shared.demo_company import resolve_demo_company

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("nexadesk.voice_demo")

MAX_TURNS = 20  # mirrors chat demo_router's MAX_MESSAGES ceiling, per-connection here


def _openai_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=settings.EMBED_API_KEY)


async def _transcribe(audio_bytes: bytes) -> str:
    """OpenAI Whisper STT. Browser MediaRecorder defaults to webm/opus."""
    client = _openai_client()
    buf = io.BytesIO(audio_bytes)
    buf.name = "audio.webm"
    response = await client.audio.transcriptions.create(model="whisper-1", file=buf)
    return response.text


async def _synthesize(text: str) -> bytes:
    """OpenAI TTS, tts-1 model. Returns MP3 bytes."""
    client = _openai_client()
    response = await client.audio.speech.create(model="tts-1", voice="alloy", input=text)
    return response.content


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
                transcript = await _transcribe(audio_bytes)
            except Exception as e:
                logger.error(f"Voice demo STT failed: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Demo is warming up — try again in a moment.",
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
                logger.error(f"Voice demo orchestrator failed: {e}")
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
                audio_reply = await _synthesize(reply)
            except Exception as e:
                logger.error(f"Voice demo TTS failed: {e}")
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
