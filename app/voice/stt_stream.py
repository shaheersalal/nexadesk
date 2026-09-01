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
import time
from typing import AsyncIterator, Callable

import websockets

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("nexadesk.voice.stt")

DEEPGRAM_WS = "wss://api.deepgram.com/v1/listen"

# Deepgram closes an idle socket; Twilio sends continuously during a call, so a
# gap this long means the call is effectively over.
IDLE_TIMEOUT = 30.0

# How long a transcript must stop changing before we treat the turn as over,
# when Deepgram has not told us itself.
#
# Deepgram does not reliably emit `speech_final` or `UtteranceEnd`. Verified
# against nova-2 with byte-identical audio, identical parameters and 20 ms
# wall-clock-accurate pacing: in roughly half of runs it emits neither, and
# instead repeats the same interim transcript about once a second, indefinitely,
# straight through five seconds of trailing silence.
#
# This handler used to deliver a turn only on those two events, so whenever they
# went missing the caller got permanent silence — the assistant had transcribed
# them perfectly and simply never replied. The events are now a fast path, not a
# guarantee: whatever text we are holding, finalised or still interim, is
# delivered once it has stopped changing for this long.
#
# A stalled transcript is not proof the caller stopped talking, and neither is
# local silence on its own: the caller can have genuinely stopped while Deepgram
# is still a second behind on what they already said. Both of those cut a live
# call in half mid-question —
#
#   Caller: Hi. What properties do you have
#   Caller: What properties do you have available in Nashville?
#
# — and the assistant answered each half separately.
#
# The reliable test uses Deepgram's own clock. Every Results message carries
# `start` + `duration`, which is the audio timestamp it has finished analysing,
# and it keeps advancing through silence. Measuring the caller's last voiced
# frame on the same audio timeline, the turn is over once Deepgram has analysed
# at least SILENCE_SECONDS of audio *past* that point — whatever they said has
# been transcribed by then, and nothing followed it.
SETTLE_SECONDS = 0.6
SILENCE_SECONDS = 0.7

# If the line is noisy enough that local silence detection never triggers, fall
# back to the transcript alone rather than never answering.
HARD_SETTLE_SECONDS = 4.0

# mu-law byte -> signed 16-bit, built once. audioop would do this but it is
# deprecated and slated for removal in 3.13, and this is ten lines.
def _build_ulaw_table() -> list[int]:
    table = []
    for byte in range(256):
        u = ~byte & 0xFF
        sign, exponent, mantissa = u & 0x80, (u >> 4) & 0x07, u & 0x0F
        magnitude = ((mantissa << 1) + 33) << exponent
        magnitude = (magnitude - 33) << 2   # conventional G.711 scale, +-32124
        table.append(-magnitude if sign else magnitude)
    return table


_ULAW = _build_ulaw_table()


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
        self._settler: asyncio.Task | None = None
        self._closed = False
        # Text held for the current turn: segments Deepgram has finalised, plus
        # the newest interim, which is all we get when it never finalises.
        self._final: list[str] = []
        self._interim = ""
        self._changed_at = 0.0
        # What the settle timer last delivered, so the late-arriving final of an
        # already-delivered utterance does not run the turn a second time.
        self._delivered = ""
        # Voice activity and Deepgram's progress, both on the audio timeline
        # rather than the wall clock, so neither is thrown off by jitter.
        self._audio_seconds = 0.0     # how much caller audio we have forwarded
        self._voice_until = 0.0       # timestamp of their last voiced frame
        self._processed_to = 0.0      # how far Deepgram says it has analysed
        self._noise_floor = 0.0

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
        self._settler = asyncio.create_task(self._settle_loop())
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _read_loop(self) -> None:
        """Consume Deepgram events and push finalised utterances onto the queue."""
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                mtype = msg.get("type")

                if mtype == "Results":
                    alt = (msg.get("channel", {}).get("alternatives") or [{}])[0]
                    text = (alt.get("transcript") or "").strip()
                    # How far into the call Deepgram has analysed. Advances even
                    # while the line is silent, which is what makes it usable as
                    # a "has it caught up yet" signal.
                    end = (msg.get("start") or 0.0) + (msg.get("duration") or 0.0)
                    self._processed_to = max(self._processed_to, end)

                    # Already delivered by the settle timer. Deepgram goes on
                    # repeating it — as an interim, and often later as a final —
                    # and every repeat would otherwise run the turn again.
                    if text and self._matches_delivered(text):
                        continue

                    if msg.get("is_final"):
                        if text:
                            self._final.append(text)
                            self._touch()
                            self._interim = ""
                        # speech_final means Deepgram's VAD saw the caller stop.
                        if msg.get("speech_final"):
                            await self._flush()
                    elif text != self._interim:
                        # Interims are the only thing we get in the failure mode
                        # described at SETTLE_SECONDS, so they are held, not
                        # discarded — a changing interim also proves the caller
                        # is still talking, which is what resets the timer.
                        self._interim = text
                        self._touch()

                elif mtype == "SpeechStarted":
                    self.speech_started.set()
                elif mtype == "UtteranceEnd":
                    # Backstop: fires when audio goes quiet without speech_final.
                    await self._flush()

        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        except Exception as exc:
            logger.error("Deepgram read loop error: %s", exc, exc_info=True)
        finally:
            await self._flush()
            await self._queue.put("")  # sentinel: stream finished

    async def _settle_loop(self) -> None:
        """
        Deliver a turn when the transcript stops changing.

        This is what makes the pipeline independent of `speech_final` and
        `UtteranceEnd`, which Deepgram withholds about half the time — see
        SETTLE_SECONDS. Without it a caller whose turn was transcribed
        perfectly is simply never answered.
        """
        try:
            while not self._closed:
                await asyncio.sleep(0.1)
                if not self._final and not self._interim:
                    continue
                idle = time.monotonic() - self._changed_at
                if idle >= HARD_SETTLE_SECONDS:
                    logger.info("Settling turn: transcript idle %.1fs", idle)
                    await self._flush()
                elif idle >= SETTLE_SECONDS and self._caller_finished():
                    logger.info(
                        "Settling turn: transcript idle %.1fs, analysed to %.1fs "
                        "vs last voice at %.1fs", idle, self._processed_to, self._voice_until)
                    await self._flush()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("STT settle loop error: %s", exc, exc_info=True)

    def _touch(self) -> None:
        self._changed_at = time.monotonic()

    def _matches_delivered(self, text: str) -> bool:
        norm = lambda s: " ".join(s.split()).casefold().rstrip(".?!,")
        return bool(self._delivered) and norm(text) == norm(self._delivered)

    async def _flush(self) -> None:
        """Hand whatever we are holding to the turn pump, as one utterance."""
        parts = [*self._final]
        if self._interim:
            parts.append(self._interim)
        # Clear before awaiting: both loops call this, and the await below is a
        # scheduling point where the other one could otherwise flush the same text.
        self._final.clear()
        self._interim = ""
        self._changed_at = 0.0

        utterance = " ".join(p for p in parts if p).strip()
        if utterance:
            self._delivered = utterance
            await self._queue.put(utterance)

    def note_audio(self, frame: bytes) -> None:
        """
        Track whether the caller is still speaking, from the audio itself.

        Position is kept in audio seconds, not wall-clock time, so it can be
        compared directly against the timestamps Deepgram reports.

        The threshold rides on a slow noise floor rather than being fixed, so a
        hissy line does not read as continuous speech.
        """
        if not frame:
            return
        self._audio_seconds += len(frame) / 8000.0
        peak = 0
        for byte in frame:
            sample = _ULAW[byte]
            if sample < 0:
                sample = -sample
            if sample > peak:
                peak = sample

        # Decay the floor upward slowly and pull it down instantly, so it tracks
        # the quietest recent audio rather than being dragged up by speech.
        self._noise_floor = min(peak, self._noise_floor * 1.02 + 1.0)
        if peak > max(self._noise_floor * 4.0, 900):
            self._voice_until = self._audio_seconds

    def _caller_finished(self) -> bool:
        """Has Deepgram analysed far enough past the caller's last word?"""
        # No audio measured (unit tests, or a track that never carried voice) —
        # don't hold the turn hostage on a signal we do not have.
        if not self._voice_until:
            return True
        return self._processed_to >= self._voice_until + SILENCE_SECONDS

    async def send(self, audio: bytes) -> None:
        """Forward one raw mulaw frame from Twilio."""
        if self._closed or not self._ws:
            return
        try:
            await self._ws.send(audio)
        except websockets.ConnectionClosed:
            self._closed = True

    def live_text(self) -> str:
        """
        What the caller is saying *right now*, before the turn is finalised.

        Used to tell a real interruption from the assistant hearing itself:
        Deepgram's voice activity flag alone cannot, because an echo trips it
        exactly like a person does.
        """
        parts = [*self._final]
        if self._interim:
            parts.append(self._interim)
        return " ".join(p for p in parts if p).strip()

    async def next_utterance(self, timeout: float | None = None) -> str | None:
        """
        One finalised utterance. None once the stream is finished.

        Raises asyncio.TimeoutError if nothing arrives in `timeout` — which is
        how the caller of this distinguishes "they have stopped for now" from
        "the call is over", and is what lets turns be coalesced.
        """
        item = await asyncio.wait_for(self._queue.get(),
                                      timeout=IDLE_TIMEOUT if timeout is None else timeout)
        return None if item == "" else item

    async def utterances(self) -> AsyncIterator[str]:
        """Yield complete caller utterances as Deepgram finalises them."""
        while True:
            try:
                item = await self.next_utterance()
            except asyncio.TimeoutError:
                logger.info("STT stream idle for %ss — ending", IDLE_TIMEOUT)
                return
            if item is None:
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
        for task in (self._settler, self._reader):
            if task:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
