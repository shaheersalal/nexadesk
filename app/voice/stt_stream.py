"""
Deepgram streaming STT over WebSocket.

Replaces the previous approach in `stt.py`, which POSTed fixed 160 ms slices of
audio to Deepgram's *pre-recorded* endpoint (AUDIT.md M1, M2). That design had
three problems:

  * ~6 HTTP round trips per second of call, each with connection overhead;
  * utterances cut on a byte boundary mid-word, so the LLM saw fragments;
  * no endpointing, so nothing knew when the caller had actually stopped talking
    — the pipeline just fired on every buffer regardless.

Streaming fixes all three. Deepgram performs voice activity detection server
side and emits `speech_final` when the caller finishes an utterance, which is
the signal to run a turn.
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Callable

import websockets

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("nexadesk.voice.stt")

DEEPGRAM_WS = "wss://api.deepgram.com/v1/listen"

# Deepgram closes an idle socket; Twilio sends continuously during a call, so a
# gap this long means the call is effectively over.
IDLE_TIMEOUT = 30.0


def _configured_default_language() -> str | None:
    """
    The language to ask for when the caller's is not yet known.

    Returns the single configured language when only one is supported, which is
    the honest thing to request rather than pretending to detect. With several
    configured it returns None, and the parameter is omitted entirely — Deepgram
    then defaults to English, which is still better than a 400 that kills the call.
    """
    langs = [x.strip() for x in (settings.SUPPORTED_LANGUAGES or "").split(",") if x.strip()]
    return langs[0] if len(langs) == 1 else None


def _build_url(language: str | None) -> str:
    params = {
        "model": settings.STT_MODEL,
        "encoding": "mulaw",
        "sample_rate": "8000",
        "channels": "1",
        "punctuate": "true",
        "smart_format": "true",
        # Interim results let us show/act on partials; endpointing + utterance_end
        # give us a reliable "caller stopped speaking" signal.
        "interim_results": "true",
        # 300ms was too eager. People pause mid-sentence to think, and at that
        # setting Deepgram called the turn finished while the caller was still
        # mid-thought — the assistant answered half a question, which reads as
        # being interrupted. 600ms is long enough to ride out a normal pause and
        # short enough not to feel laggy, and the streaming synthesis added on
        # the other side more than pays back the extra wait.
        "endpointing": "600",
        "utterance_end_ms": "1400",
        "vad_events": "true",
    }
    # Never send detect_language on the streaming socket.
    #
    # Deepgram rejects it outright with HTTP 400 — verified against nova-2 and
    # nova-3, while the same URL with `language=` or with no language parameter
    # at all connects fine. That 400 was thrown from DeepgramStream.__aenter__
    # before the greeting was ever synthesised, so the handler aborted and every
    # single inbound call was answered with silence until the caller hung up.
    #
    # It fired on every call, not an unlucky few: stt_language is None whenever
    # session.language_confirmed is False, which it always is on a fresh call.
    if not language:
        language = _configured_default_language()
    if language:
        params["language"] = language
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{DEEPGRAM_WS}?{query}"


class DeepgramStream:
    """
    A live transcription socket for one phone call.

    Usage:
        async with DeepgramStream(language="en") as stt:
            await stt.send(mulaw_bytes)          # from Twilio media frames
            async for utterance in stt.utterances():
                ...                              # complete caller turns only
    """

    def __init__(self, language: str | None = "en"):
        self._language = language
        # Set the moment Deepgram's VAD hears speech. The caller talking over
        # the assistant is the assistant's cue to stop, not something to talk
        # through — see the barge-in handling in voice/router.py.
        self.speech_started = asyncio.Event()
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._reader: asyncio.Task | None = None
        self._closed = False

    async def __aenter__(self) -> "DeepgramStream":
        if not settings.STT_API_KEY:
            raise RuntimeError("STT_API_KEY is not configured")
        self._ws = await websockets.connect(
            _build_url(self._language),
            additional_headers={"Authorization": f"Token {settings.STT_API_KEY}"},
            ping_interval=5,
            ping_timeout=20,
        )
        self._reader = asyncio.create_task(self._read_loop())
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _read_loop(self) -> None:
        """Consume Deepgram events and push finalised utterances onto the queue."""
        buffer: list[str] = []
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                mtype = msg.get("type")

                if mtype == "Results":
                    alt = (msg.get("channel", {}).get("alternatives") or [{}])[0]
                    text = (alt.get("transcript") or "").strip()
                    if not text:
                        continue
                    if msg.get("is_final"):
                        buffer.append(text)
                        # speech_final means Deepgram's VAD saw the caller stop.
                        if msg.get("speech_final"):
                            await self._flush(buffer)
                elif mtype == "SpeechStarted":
                    self.speech_started.set()
                elif mtype == "UtteranceEnd":
                    # Backstop: fires when audio goes quiet without speech_final.
                    await self._flush(buffer)

        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        except Exception as exc:
            logger.error("Deepgram read loop error: %s", exc, exc_info=True)
        finally:
            if buffer:
                await self._flush(buffer)
            await self._queue.put("")  # sentinel: stream finished

    async def _flush(self, buffer: list[str]) -> None:
        if not buffer:
            return
        utterance = " ".join(buffer).strip()
        buffer.clear()
        if utterance:
            await self._queue.put(utterance)

    async def send(self, audio: bytes) -> None:
        """Forward one raw mulaw frame from Twilio."""
        if self._closed or not self._ws:
            return
        try:
            await self._ws.send(audio)
        except websockets.ConnectionClosed:
            self._closed = True

    async def utterances(self) -> AsyncIterator[str]:
        """Yield complete caller utterances as Deepgram finalises them."""
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=IDLE_TIMEOUT)
            except asyncio.TimeoutError:
                logger.info("STT stream idle for %ss — ending", IDLE_TIMEOUT)
                return
            if item == "":
                return
            yield item

    async def close(self) -> None:
        self._closed = True
        if self._ws:
            try:
                # CloseStream tells Deepgram to flush anything pending.
                await self._ws.send(json.dumps({"type": "CloseStream"}))
            except Exception:
                pass
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except (asyncio.CancelledError, Exception):
                pass
