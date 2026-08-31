"""
Deepgram does not reliably end an utterance.

Verified against nova-2 with byte-identical audio, identical parameters and
20 ms wall-clock-accurate pacing: in roughly half of runs it emits neither
`speech_final` nor `UtteranceEnd`, and instead repeats the same interim
transcript about once a second, indefinitely, through five seconds of trailing
silence.

The call handler used to run a turn only on those two events, so when they went
missing the caller was met with permanent silence on a call that had been
transcribed perfectly. These tests pin the fallback that fixes it.
"""
import asyncio
import json

import pytest

from app.voice import stt_stream
from app.voice.stt_stream import DeepgramStream


class FakeSocket:
    """Yields canned Deepgram frames, then stays open like the real one does."""

    def __init__(self, frames, hold=2.0):
        self._frames = frames
        self._hold = hold

    async def __aiter__(self):  # pragma: no cover - replaced below
        raise NotImplementedError

    def __aiter__(self):
        async def gen():
            for delay, frame in self._frames:
                await asyncio.sleep(delay)
                yield json.dumps(frame)
            await asyncio.sleep(self._hold)
        return gen()


def results(transcript, *, is_final=False, speech_final=False, end=None):
    """
    One Deepgram Results frame.

    `end` is the audio timestamp Deepgram has analysed up to. It is what the
    settle logic uses to tell "the caller stopped" from "Deepgram has not caught
    up yet", so it defaults to a value far enough ahead that tests which are not
    about that distinction behave as if it has caught up.
    """
    return {
        "type": "Results",
        "is_final": is_final,
        "speech_final": speech_final,
        "start": 0.0,
        "duration": 9999.0 if end is None else end,
        "channel": {"alternatives": [{"transcript": transcript}]},
    }


async def drive(frames, settle=0.25, collect_for=1.6):
    """Run the stream's loops over canned frames and return delivered turns."""
    stream = DeepgramStream(language="en")
    stream._ws = FakeSocket(frames)
    stream._reader = asyncio.create_task(stream._read_loop())
    stream._settler = asyncio.create_task(stream._settle_loop())

    got = []

    async def collect():
        async for utterance in stream.utterances():
            got.append(utterance)

    task = asyncio.create_task(collect())
    await asyncio.sleep(collect_for)
    stream._closed = True
    task.cancel()
    for t in (stream._settler, stream._reader):
        t.cancel()
    return got


@pytest.fixture(autouse=True)
def _fast_settle(monkeypatch):
    monkeypatch.setattr(stt_stream, "SETTLE_SECONDS", 0.25)


@pytest.mark.asyncio
async def test_turn_is_delivered_when_deepgram_never_finalises():
    """The failure mode that silenced the phone line: interims only, forever."""
    line = "I am looking for a two bedroom in Nashville"
    frames = [(0.02, results(line[:12])), (0.02, results(line))]
    # Deepgram then repeats the identical interim, which is all it ever sends.
    frames += [(0.1, results(line)) for _ in range(8)]

    got = await drive(frames)

    assert got == [line], f"expected exactly one turn, got {got}"


@pytest.mark.asyncio
async def test_repeated_interims_do_not_replay_the_same_turn():
    """Each repeat used to look like new text once the buffer had been cleared."""
    line = "hello there"
    frames = [(0.02, results(line))] + [(0.1, results(line)) for _ in range(12)]

    got = await drive(frames, collect_for=1.8)

    assert got == [line], f"turn was delivered {len(got)} times: {got}"


@pytest.mark.asyncio
async def test_late_final_after_a_settled_turn_is_not_replayed():
    """Deepgram often finalises text the settle timer already delivered."""
    line = "book me a viewing on Thursday"
    frames = [(0.02, results(line))]
    frames += [(0.1, results(line)) for _ in range(5)]
    frames += [(0.05, results(line + ".", is_final=True, speech_final=True))]

    got = await drive(frames, collect_for=1.6)

    assert got == [line], f"turn was delivered {len(got)} times: {got}"


@pytest.mark.asyncio
async def test_speech_final_still_delivers_immediately():
    """The fast path must stay fast: no waiting on the settle timer."""
    frames = [(0.02, results("what is the price", is_final=True, speech_final=True))]

    got = await drive(frames, collect_for=0.15)   # well under SETTLE_SECONDS

    assert got == ["what is the price"]


@pytest.mark.asyncio
async def test_growing_interim_does_not_cut_the_caller_off():
    """A transcript still being extended is a caller still talking."""
    frames = [
        (0.02, results("I would")),
        (0.15, results("I would like")),
        (0.15, results("I would like to book")),
        (0.15, results("I would like to book a viewing")),
    ]

    # Long enough that a timer keyed on anything but *change* would have fired.
    got = await drive(frames, collect_for=1.2)

    assert got == ["I would like to book a viewing"], got


# --- local voice activity ---------------------------------------------------
#
# A stalled transcript is not proof the caller stopped. On a live call the timer
# fired mid-sentence and split one question into two turns, which the assistant
# answered separately:
#
#   Caller: Hi. What do you have
#   Caller: properties do you have available in Nashville?
#
# So settling also requires the caller's audio to have gone quiet.

SPEECH = bytes([0x00, 0x80]) * 80    # loud mu-law frame
SILENCE = b"\xff" * 160


@pytest.mark.asyncio
async def test_stalled_transcript_does_not_settle_while_deepgram_lags():
    """
    The live failure: the caller has stopped, but Deepgram is still a second
    behind on what they already said, so the text on hand is only half of it.
    """
    line = "Hi. What do you have"
    # Deepgram has only analysed up to 2.0s; the caller spoke until 2.9s.
    frames = [(0.02, results(line, end=2.0))] + [(0.1, results(line, end=2.0)) for _ in range(14)]

    stream = DeepgramStream(language="en")
    stream._ws = FakeSocket(frames)
    stream._reader = asyncio.create_task(stream._read_loop())
    stream._settler = asyncio.create_task(stream._settle_loop())

    got = []

    async def collect():
        async for utterance in stream.utterances():
            got.append(utterance)

    # 2.9s of caller speech on the audio timeline.
    for _ in range(int(2.9 / 0.02)):
        stream.note_audio(SPEECH)

    task = asyncio.create_task(collect())
    await asyncio.sleep(1.0)          # well past SETTLE_SECONDS
    stream._closed = True
    for t in (task, stream._settler, stream._reader):
        t.cancel()

    assert got == [], f"cut the caller off while Deepgram was still behind: {got}"


@pytest.mark.asyncio
async def test_settles_once_deepgram_has_analysed_past_the_last_word():
    line = "Hi. What do you have available in Nashville"
    # Caller spoke until 2.9s; Deepgram works past it, to 3.7s.
    frames = [(0.02, results(line, end=2.9))]
    frames += [(0.1, results(line, end=3.0 + i * 0.4)) for i in range(6)]

    stream = DeepgramStream(language="en")
    stream._ws = FakeSocket(frames)
    stream._reader = asyncio.create_task(stream._read_loop())
    stream._settler = asyncio.create_task(stream._settle_loop())

    got = []

    async def collect():
        async for utterance in stream.utterances():
            got.append(utterance)

    for _ in range(int(2.9 / 0.02)):
        stream.note_audio(SPEECH)

    task = asyncio.create_task(collect())
    await asyncio.sleep(1.2)
    stream._closed = True
    for t in (task, stream._settler, stream._reader):
        t.cancel()

    assert got == [line], f"expected one settled turn, got {got}"


def test_noise_floor_adapts_so_a_hissy_line_is_not_heard_as_speech():
    """
    A constant low-level hiss must stop counting as voice once the floor has
    settled, otherwise a noisy line never goes quiet and the turn never lands.

    Asserted on _last_voice_at rather than the clock: the point is that hiss
    stops *registering*, not that time passes.
    """
    stream = DeepgramStream(language="en")
    hiss = bytes([0x60, 0xE0] * 80)      # ~+-372, well above pure silence

    for _ in range(400):                 # let the floor climb to the hiss level
        stream.note_audio(hiss)
    settled = stream._voice_until

    for _ in range(50):
        stream.note_audio(hiss)
    assert stream._voice_until == settled, "steady line noise still read as speech"

    # Real speech over that same noisy line must still register.
    stream.note_audio(bytes([0x00, 0x80] * 80))
    assert stream._voice_until > settled, "speech was masked by the noise floor"
