"""
TTS via OpenAI tts-1 (uses EMBED_API_KEY — same key as embeddings).
Multilingual: pass text in any language, the model speaks it in that language.
~200ms response, high quality, outputs MP3 bytes directly.
No local model, no ffmpeg, no API key beyond the existing OpenAI key.
"""
import asyncio
import logging

logger = logging.getLogger("nexadesk.voice_demo")


async def synthesize(text: str, language: str = "en") -> bytes:
    """Synthesize text to MP3 bytes using OpenAI tts-1. language param is unused
    (tts-1 auto-detects language from the text itself)."""
    from openai import AsyncOpenAI
    from app.config import get_settings

    s = get_settings()
    client = AsyncOpenAI(api_key=s.EMBED_API_KEY)

    try:
        response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",          # neutral, works well across languages
            input=text,
            response_format="mp3",
        )
        return response.content
    except Exception as e:
        logger.error("tts-1 synthesis failed: %s", e)
        return b""


async def warmup() -> None:
    """No warmup needed — cloud API, no local model to load."""
    pass
