"""
Deepgram STT client — streaming transcription over WebSocket.
We use the pre-recorded endpoint for audio chunks received from Twilio
(Twilio sends 8kHz mulaw audio; we transcribe each chunk as it arrives).
"""
import base64
import asyncio
from typing import AsyncGenerator

import httpx

from app.config import get_settings

settings = get_settings()

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


async def transcribe_audio_chunk(audio_bytes: bytes, language: str = "en") -> str:
    """
    Send a raw audio chunk to Deepgram for transcription.
    audio_bytes: raw mulaw/8000Hz audio (from Twilio Media Stream)
    Returns the transcript string (may be empty if no speech detected).
    """
    params = {
        "model": settings.STT_MODEL,
        "language": language,
        "encoding": "mulaw",
        "sample_rate": "8000",
        "punctuate": "true",
        "smart_format": "true",
    }
    headers = {
        "Authorization": f"Token {settings.STT_API_KEY}",
        "Content-Type": "audio/mulaw",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            DEEPGRAM_URL,
            content=audio_bytes,
            params=params,
            headers=headers,
        )
        if response.status_code != 200:
            return ""
        data = response.json()

    try:
        return data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError):
        return ""


async def transcribe_mulaw_b64(audio_b64: str, language: str = "en") -> str:
    """Transcribe base64-encoded mulaw audio (format Twilio sends over WebSocket)."""
    audio_bytes = base64.b64decode(audio_b64)
    if len(audio_bytes) < 160:  # Too small — likely silence
        return ""
    return await transcribe_audio_chunk(audio_bytes, language)
