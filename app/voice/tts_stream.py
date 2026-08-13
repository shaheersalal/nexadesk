"""
Sentence-chunked streaming TTS.

The old pipeline was strictly sequential: wait for the whole LLM reply, then
synthesise the whole thing, then send it. With a 150-token reply that is roughly
1-2 s of LLM time before a single byte of audio exists, on top of STT and
retrieval — around 2.5-4.5 s of dead air after the caller stops talking. Callers
start talking over the bot at about 1.5 s.

Here we consume the LLM's token stream, cut it at clause boundaries, and
synthesise each fragment as soon as it is complete. The caller starts hearing
the first sentence while the model is still writing the second, which collapses
perceived latency to roughly "time to first sentence".
"""
import asyncio
import logging
import re
from typing import AsyncIterator

from app.voice.tts import synthesize_to_mulaw

logger = logging.getLogger("nexadesk.voice.tts")

# Cut on sentence-ending punctuation followed by whitespace. Kept deliberately
# simple — this runs per token, so it must be cheap.
_BOUNDARY = re.compile(r"(?<=[.!?])\s+")

# Don't synthesise a fragment shorter than this; "Yes." on its own costs a whole
# TTS round trip to say almost nothing. Merge it into the next chunk instead.
MIN_CHUNK_CHARS = 25

# Force a flush if the model produces a long run with no sentence punctuation,
# so we never sit on a growing buffer waiting for a full stop that isn't coming.
MAX_CHUNK_CHARS = 220


async def sentence_chunks(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """
    Regroup a token stream into speakable fragments.

    Yields as soon as a fragment is worth speaking, rather than waiting for the
    generation to finish.
    """
    buffer = ""
    async for token in tokens:
        if not token:
            continue
        buffer += token

        while True:
            if len(buffer) >= MAX_CHUNK_CHARS:
                # No punctuation in sight — cut at the last space so we don't
                # split a word in half.
                cut = buffer.rfind(" ", 0, MAX_CHUNK_CHARS)
                if cut <= 0:
                    cut = MAX_CHUNK_CHARS
                chunk, buffer = buffer[:cut].strip(), buffer[cut:].lstrip()
                if chunk:
                    yield chunk
                continue

            # Walk the boundaries in order and take the first one that leaves a
            # fragment long enough to be worth its own TTS request. Stopping at
            # the *first* boundary regardless meant a short opener like
            # "Hello there!" blocked every later split, and the whole reply came
            # out as one chunk — silently defeating the streaming.
            split_at = None
            for match in _BOUNDARY.finditer(buffer):
                if len(buffer[:match.start()].strip()) >= MIN_CHUNK_CHARS:
                    split_at = match
                    break
            if split_at is None:
                break

            candidate = buffer[:split_at.start()].strip()
            buffer = buffer[split_at.end():]
            if candidate:
                yield candidate

    tail = buffer.strip()
    if tail:
        yield tail


async def stream_speech(tokens: AsyncIterator[str]) -> AsyncIterator[tuple[str, bytes]]:
    """
    Turn an LLM token stream into (text, mulaw_audio) pairs, in order.

    Synthesis of chunk N+1 is kicked off while chunk N is still being sent to
    Twilio, but results are yielded strictly in order — audio played out of
    sequence would be worse than audio played slightly later.
    """
    pending: asyncio.Task | None = None
    pending_text = ""

    async for chunk in sentence_chunks(tokens):
        # Start this chunk synthesising immediately.
        task = asyncio.create_task(synthesize_to_mulaw(chunk))

        # Yield the previous one while this is in flight.
        if pending is not None:
            try:
                audio = await pending
            except Exception as exc:
                logger.error("TTS chunk failed: %s", exc)
                audio = b""
            if audio:
                yield pending_text, audio

        pending, pending_text = task, chunk

    if pending is not None:
        try:
            audio = await pending
        except Exception as exc:
            logger.error("TTS chunk failed: %s", exc)
            audio = b""
        if audio:
            yield pending_text, audio
