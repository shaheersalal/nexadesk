"""
Batch transcription for a complete uploaded audio file.

This is the correct use of Deepgram's pre-recorded endpoint: the demo widget
records an utterance in the browser and uploads the whole blob, so there is no
stream to follow and nothing to endpoint. The live call path uses
`stt_stream.py` instead — sending fixed slices of a *live* call to this endpoint
was the mistake that streaming replaced (AUDIT.md M2).
"""
import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("nexadesk.voice.stt")

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


async def transcribe_file(
    audio: bytes,
    content_type: str = "audio/webm",
    language: str | None = "en",
) -> str:
    """
    Transcribe a complete audio file. Returns the transcript, or "" on failure.

    `language=None` asks Deepgram to auto-detect, which is what the demo's
    "Auto" language option sends.
    """
    if not settings.STT_API_KEY:
        logger.error("STT_API_KEY not configured — cannot transcribe")
        return ""

    params = {
        "model": settings.STT_MODEL,
        "punctuate": "true",
        "smart_format": "true",
    }
    if language:
        params["language"] = language
    else:
        params["detect_language"] = "true"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                DEEPGRAM_URL,
                content=audio,
                params=params,
                headers={
                    "Authorization": f"Token {settings.STT_API_KEY}",
                    "Content-Type": content_type,
                },
            )
        if response.status_code != 200:
            logger.error(
                "Deepgram transcription failed: %s %s",
                response.status_code,
                response.text[:300],
            )
            return ""
        data = response.json()
        return data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError):
        logger.warning("Deepgram returned no transcript alternatives")
        return ""
    except Exception as exc:
        logger.error("Deepgram transcription error: %s", exc)
        return ""
