"""
ElevenLabs TTS client â€” streaming audio synthesis.
Returns audio bytes (MP3) that get sent back to Twilio.
"""
import asyncio
import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("nexadesk.voice")

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"


async def synthesize(text: str, voice_id: str | None = None) -> bytes:
    """
    Convert text to speech. Returns MP3 bytes.
    Falls back to Twilio <Say> if ElevenLabs is not configured.
    """
    if not settings.TTS_API_KEY:
        return b""  # Caller will use Twilio <Say> fallback

    vid = voice_id or settings.TTS_VOICE_ID
    url = f"{ELEVENLABS_BASE}/text-to-speech/{vid}"

    payload = {
        "text": text,
        "model_id": settings.TTS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": settings.TTS_API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error(f"ElevenLabs TTS request failed: {response.status_code} {response.text}")
            return b""
        return response.content


async def synthesize_to_mulaw(text: str) -> bytes:
    """
    Synthesize and convert to 8 kHz mulaw for Twilio playback.

    ffmpeg is still needed to decode ElevenLabs' MP3, but it is now run via
    asyncio's subprocess API instead of a blocking `subprocess.run` inside an
    async function â€” the old form stalled the event loop for the whole
    conversion, on every single spoken reply, for every concurrent call
    (AUDIT.md, ruff ASYNC221).
    """
    mp3_bytes = await synthesize(text)
    if not mp3_bytes:
        return b""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", "pipe:0", "-ar", "8000", "-ac", "1",
            "-f", "mulaw", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=mp3_bytes), timeout=10
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error("TTS mulaw conversion timed out after 10s")
            return b""

        if proc.returncode != 0:
            logger.error(
                "ffmpeg exited %s during mulaw conversion: %s",
                proc.returncode,
                stderr.decode(errors="replace")[:400],
            )
            return b""
        return stdout
    except FileNotFoundError:
        logger.error("ffmpeg not found on PATH â€” cannot convert TTS audio for Twilio")
        return b""
    except Exception as e:
        logger.error(f"TTS mulaw conversion failed: {e}")
        return b""
