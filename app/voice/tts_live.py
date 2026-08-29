"""
Live streaming speech synthesis over Deepgram's Speak WebSocket.

Replaces the clause-at-a-time HTTP approach on the phone path. That version cut
the reply on sentence boundaries and made one synthesis request per fragment,
which had two audible costs:

  * A seam at every boundary. Each fragment was rendered independently, so
    prosody reset mid-sentence and the joins were hearable — the "breaking"
    callers notice.
  * A gap whenever synthesis lost the race. Playback of a short clause takes
    around a second; Aura-2 needs roughly 0.22s per word plus a round trip, so
    any network wobble meant the caller heard silence in the middle of a
    sentence while the next fragment was still being made.

The socket takes text as it is produced and returns a continuous audio stream,
so there is one uninterrupted rendering per turn. It emits mulaw at 8 kHz
directly, which is exactly Twilio's wire format — no audioop conversion.
"""
import asyncio
import json
import logging
from typing import AsyncIterator

import websockets

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("nexadesk.voice.tts")

SPEAK_WS = "wss://api.deepgram.com/v1/speak"

# The phone line uses an Aura-1 voice. On an 8 kHz mulaw channel the difference
# from Aura-2 is largely masked by the codec, while Aura-1 returns first audio
# roughly three times sooner — and on a call, latency IS quality. The web demo,
# which is full bandwidth and where the voice is actually scrutinised, keeps
# Aura-2.
PHONE_VOICE = "aura-asteria-en"


def _url(voice: str | None = None) -> str:
    return (
        f"{SPEAK_WS}?model={voice or PHONE_VOICE}"
        "&encoding=mulaw&sample_rate=8000&container=none"
    )


class SpeakStream:
    """
    One synthesis socket for one spoken turn.

    Usage:
        async with SpeakStream() as speak:
            await speak.feed("Some text as it arrives")
            await speak.finish()
            async for audio in speak.audio():
                ...
    """

    def __init__(self, voice: str | None = None):
        self._voice = voice
        self._ws = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._reader: asyncio.Task | None = None
        self._done = asyncio.Event()

    async def __aenter__(self) -> "SpeakStream":
        self._ws = await websockets.connect(
            _url(self._voice),
            additional_headers={"Authorization": f"Token {settings.STT_API_KEY}"},
            open_timeout=10,
        )
        self._reader = asyncio.create_task(self._read())
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _read(self) -> None:
        try:
            async for message in self._ws:
                if isinstance(message, (bytes, bytearray)):
                    await self._queue.put(bytes(message))
                else:
                    try:
                        kind = json.loads(message).get("type")
                    except Exception:
                        continue
                    if kind in ("Flushed", "Close"):
                        break
        except Exception as exc:
            logger.warning("Speak socket read ended: %s", exc)
        finally:
            self._done.set()
            await self._queue.put(None)   # sentinel

    async def feed(self, text: str) -> None:
        """Send text to be spoken. Safe to call repeatedly as tokens arrive."""
        if not text.strip() or self._ws is None:
            return
        await self._ws.send(json.dumps({"type": "Speak", "text": text}))

    async def finish(self) -> None:
        """Tell Deepgram no more text is coming and to render what is buffered."""
        if self._ws is not None:
            await self._ws.send(json.dumps({"type": "Flush"}))

    async def audio(self) -> AsyncIterator[bytes]:
        """Yield mulaw chunks as they are produced."""
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                return
            yield chunk

    async def close(self) -> None:
        if self._reader:
            self._reader.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None


async def speak_tokens(tokens: AsyncIterator[str]) -> AsyncIterator[bytes]:
    """
    Feed an LLM token stream into synthesis and yield mulaw audio continuously.

    Text goes in as it is generated and audio comes back while the model is
    still writing, so the caller hears the opening words before the reply is
    finished — the same win the clause chunker was after, without the seams it
    introduced.

    Whole words are sent rather than raw tokens: a token boundary can split a
    word, and Deepgram would pronounce the halves separately.
    """
    async with SpeakStream() as speak:
        async def pump() -> None:
            buffer = ""
            try:
                async for token in tokens:
                    if not token:
                        continue
                    buffer += token
                    # flush on whitespace so only complete words are sent
                    if buffer[-1].isspace():
                        await speak.feed(buffer)
                        buffer = ""
                if buffer.strip():
                    await speak.feed(buffer)
            finally:
                await speak.finish()

        pump_task = asyncio.create_task(pump())
        try:
            async for chunk in speak.audio():
                yield chunk
        finally:
            if not pump_task.done():
                pump_task.cancel()
