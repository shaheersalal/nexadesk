"""
Text-to-speech with pluggable providers.

Two backends, chosen by TTS_PROVIDER:

  deepgram    Aura-2. Fast (sub-200ms first byte) and roughly 5-7x cheaper than
              ElevenLabs, but has no Arabic or Urdu voice at all.
  elevenlabs  More expressive, and the only option for ar/ur.

TTS_PROVIDER="auto" (the default) prefers ElevenLabs when TTS_API_KEY is set and
otherwise falls back to Deepgram, so adding an ElevenLabs key later switches
providers without a code change.

Deepgram can return 8 kHz linear16 directly, which the Twilio path converts to
mulaw with `audioop` — no ffmpeg subprocess at all. ElevenLabs only returns
compressed formats, so that path still shells out to ffmpeg to decode.
"""
import asyncio
import audioop
import logging
import re

import httpx

from app.shared.http import client as http_client

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("nexadesk.voice")

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
DEEPGRAM_SPEAK = "https://api.deepgram.com/v1/speak"

# Deepgram's TTS and STT share one API key; STT_API_KEY is where it lives.
DEEPGRAM_DEFAULT_VOICE = "aura-2-apollo-en"


def _provider() -> str:
    """Resolve the active TTS provider, or "" when none is usable."""
    choice = (settings.TTS_PROVIDER or "auto").strip().lower()

    if choice == "elevenlabs":
        return "elevenlabs" if settings.TTS_API_KEY else ""
    if choice == "deepgram":
        return "deepgram" if settings.STT_API_KEY else ""

    # auto
    if settings.TTS_API_KEY:
        return "elevenlabs"
    if settings.STT_API_KEY:
        return "deepgram"
    return ""


def _deepgram_voice(voice_id: str | None) -> str:
    """
    Pick the Aura model name.

    TTS_VOICE_ID is shared with ElevenLabs, where it holds an opaque voice id
    rather than a model name, so anything that doesn't look like an Aura model
    is ignored in favour of the default.
    """
    candidate = (voice_id or settings.TTS_VOICE_ID or "").strip()
    if candidate.startswith("aura"):
        return candidate
    return DEEPGRAM_DEFAULT_VOICE


# ── ElevenLabs ────────────────────────────────────────────────────────────────

async def _elevenlabs(text: str, voice_id: str | None) -> bytes:
    vid = voice_id or settings.TTS_VOICE_ID
    if not vid:
        logger.error("TTS_VOICE_ID is not set — ElevenLabs needs a voice id")
        return b""

    try:
        response = await http_client().post(
            f"{ELEVENLABS_BASE}/text-to-speech/{vid}",
            timeout=15.0,
            json={
                "text": text,
                "model_id": settings.TTS_MODEL,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            headers={"xi-api-key": settings.TTS_API_KEY,
                     "Content-Type": "application/json"},
        )
    except Exception as exc:
        logger.error("ElevenLabs TTS request failed: %s", exc)
        return b""

    if response.status_code != 200:
        logger.error("ElevenLabs TTS %s: %s", response.status_code, response.text[:300])
        return b""
    return response.content


# ── Deepgram Aura ─────────────────────────────────────────────────────────────

async def _deepgram(text: str, voice_id: str | None, *, telephony: bool = False) -> bytes:
    """
    Synthesize with Aura.

    `telephony=True` asks for raw 8 kHz linear16 (headerless), which is one
    `audioop.lin2ulaw` away from what Twilio wants. Otherwise returns MP3 for
    browser playback.
    """
    params = {"model": _deepgram_voice(voice_id)}
    if telephony:
        params |= {"encoding": "linear16", "sample_rate": "8000", "container": "none"}
    else:
        params |= {"encoding": "mp3"}

    try:
        response = await http_client().post(
            DEEPGRAM_SPEAK,
            timeout=20.0,
            params=params,
            json={"text": text},
            headers={"Authorization": f"Token {settings.STT_API_KEY}",
                     "Content-Type": "application/json"},
        )
    except Exception as exc:
        logger.error("Deepgram TTS request failed: %s", exc)
        return b""

    if response.status_code != 200:
        logger.error("Deepgram TTS %s: %s", response.status_code, response.text[:300])
        return b""
    return response.content


# ── Public API ────────────────────────────────────────────────────────────────

async def synthesize(text: str, voice_id: str | None = None) -> bytes:
    """
    Convert text to compressed audio (MP3) for browser playback.

    Returns b"" when no provider is configured; callers treat that as "show the
    text, play nothing" rather than an error.
    """
    if not text.strip():
        return b""

    provider = _provider()
    if provider == "elevenlabs":
        return await _elevenlabs(text, voice_id)
    if provider == "deepgram":
        return await _deepgram(text, voice_id)

    logger.warning("No TTS provider configured — set TTS_API_KEY or STT_API_KEY")
    return b""


async def synthesize_to_mulaw(text: str) -> bytes:
    """
    Synthesize 8 kHz mulaw for Twilio Media Streams.

    Deepgram returns 8 kHz PCM directly, so the conversion is a pure-Python
    `audioop` call. ElevenLabs only emits compressed audio, so that path must
    decode via ffmpeg — run through asyncio's subprocess API, since a blocking
    `subprocess.run` here stalled the event loop for every concurrent call
    (ruff ASYNC221).
    """
    if not text.strip():
        return b""

    provider = _provider()

    if provider == "deepgram":
        pcm = await _deepgram(text, None, telephony=True)
        if not pcm:
            return b""
        try:
            return audioop.lin2ulaw(pcm, 2)
        except Exception as exc:
            logger.error("mulaw conversion failed: %s", exc)
            return b""

    if provider != "elevenlabs":
        return b""

    mp3_bytes = await _elevenlabs(text, None)
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
        logger.error("ffmpeg not found on PATH — cannot convert ElevenLabs audio for Twilio")
        return b""
    except Exception as exc:
        logger.error("TTS mulaw conversion failed: %s", exc)
        return b""


# ── Parallel clause synthesis (browser paths) ─────────────────────────────────

_CLAUSE_SPLIT = re.compile(r"(?<=[.!?,;:])\s+")


def _clauses(text: str, target: int = 3) -> list[str]:
    """
    Split a reply into roughly `target` clause groups on punctuation.

    Groups are merged up to a minimum length so synthesis is not fragmented into
    two-word requests, which sound clipped when the pieces are joined.
    """
    parts = [p for p in _CLAUSE_SPLIT.split(text.strip()) if p.strip()]
    if len(parts) <= 1:
        return parts or [text]
    floor = max(28, len(text) // target)
    out: list[str] = []
    for p in parts:
        if out and len(out[-1]) + len(p) < floor:
            out[-1] += " " + p
        else:
            out.append(p)
    return out




async def synthesize_browser(text: str, voice_id: str | None = None) -> tuple[bytes, str]:
    """
    Synthesize for browser playback. Returns (audio_bytes, mime_type).

    Aura-2 generation time scales with the length of the text, and it is slow:
    measured at ~5.3s for a 22-word reply, which was ~70% of the demo's entire
    turn while transcription and the model together took under two seconds.

    Splitting the reply on clause boundaries and synthesizing the pieces
    CONCURRENTLY cuts that roughly in half without touching voice quality —
    Aura-1 voices are ~3.5x faster still, but noticeably more synthetic, and the
    web demo is the one surface where quality is not up for trade.

    The pieces come back as MP3 and are joined byte-wise. MP3 is a stream of
    self-contained frames — each piece here begins on a frame sync — so the
    result decodes as one file; verified in a browser, which reports the joined
    duration and no decode error. Raw PCM would also join, but at 16 kHz it is
    ~376 KB against 61 KB for the same reply, which is a poor trade on mobile.

    Falls back to the single-shot path for ElevenLabs and for any failure.
    """
    if not text.strip():
        return b"", "audio/mpeg"

    if _provider() != "deepgram":
        return await synthesize(text, voice_id), "audio/mpeg"

    pieces = _clauses(text)
    if len(pieces) < 2:
        return await synthesize(text, voice_id), "audio/mpeg"

    try:
        parts = await asyncio.gather(
            *(_deepgram_mp3(p, voice_id) for p in pieces)
        )
    except Exception as exc:
        logger.warning("Parallel synthesis failed (%s) — falling back", exc)
        return await synthesize(text, voice_id), "audio/mpeg"

    if not all(parts):
        return await synthesize(text, voice_id), "audio/mpeg"

    return b"".join(parts), "audio/mpeg"


async def _deepgram_mp3(text: str, voice_id: str | None) -> bytes:
    """One clause as MP3, whose frames concatenate with the neighbouring pieces."""
    response = await http_client().post(
        DEEPGRAM_SPEAK,
        timeout=20.0,
        params={
            "model": _deepgram_voice(voice_id),
            "encoding": "mp3",
        },
        json={"text": text},
        headers={"Authorization": f"Token {settings.STT_API_KEY}",
                 "Content-Type": "application/json"},
    )
    if response.status_code != 200:
        logger.error("Deepgram TTS %s: %s", response.status_code, response.text[:200])
        return b""
    return response.content
