"""
Whose words are whose, and how many of them make one turn.

The pipeline transcribes continuously, including while the assistant is
speaking — that is what stops a caller's words going unheard. These tests pin
the two things that has to get right: not mistaking the assistant's own voice
coming back down the line for the caller, and not turning one question into two
answers.
"""
import asyncio

import pytest

from app.voice.turn_taking import SpokenLog, collect_turn, merge_utterances

REPLY = ("We have three properties available in Nashville right now, "
         "starting at four hundred and forty thousand dollars.")


def speaking_log(text=REPLY, seconds=6.0):
    """A log for an assistant that is mid-sentence, with `seconds` left to play."""
    log = SpokenLog()
    log.note_spoken(text)
    log.note_audio_sent(int(seconds * 8000))
    return log


# --- attribution ------------------------------------------------------------

def test_verbatim_echo_is_recognised_as_our_own():
    log = speaking_log()
    assert log.is_echo("we have three properties available in nashville right now")


def test_garbled_echo_is_still_recognised():
    """Echo reaches Deepgram degraded, so the match is never exact."""
    log = speaking_log()
    assert log.is_echo("we have three properties available in nashville right no")
    assert log.is_echo("have three properties in nashville starting at four hundred")


def test_a_real_question_sharing_our_vocabulary_is_not_suppressed():
    """The caller will reuse our words. That is not an echo."""
    log = speaking_log()
    for question in [
        "do you have anything cheaper in austin",
        "are any of those properties available to view on thursday",
        "what about three bedroom places under five hundred thousand",
    ]:
        assert not log.is_echo(question), question


def test_a_short_answer_is_never_dropped_as_echo():
    """
    A caller's "yes" while the assistant is still talking is the most
    meaningful word in the call, and it shares every word with something.
    """
    log = speaking_log()
    for short in ["yes", "no", "sure", "go on", "the first one"]:
        assert not log.is_echo(short), short


def test_a_short_utterance_we_verbatim_just_said_is_still_echo():
    log = speaking_log("Would you like me to book a viewing?")
    assert log.is_echo("book a viewing")


def test_our_words_stop_counting_once_we_have_stopped_speaking():
    """Later in the call the caller may quote us, and must be answered."""
    log = speaking_log()
    log._playing_until -= 20.0             # finished playing long ago
    assert not log.is_echo("we have three properties available in nashville")


def test_echo_is_caught_for_as_long_as_the_audio_is_still_playing():
    """
    The bug this replaced: the window was keyed on when audio was *sent* to
    Twilio, but we push synthesis far faster than 8 kHz playback. The assistant
    thought it had stopped talking seconds before the caller stopped hearing
    it, so the echo of its own greeting arrived outside the window and was
    answered as though the caller had said it.
    """
    log = SpokenLog()
    log.note_spoken(REPLY)
    log.note_audio_sent(8000 * 9)          # nine seconds of audio, sent at once
    assert log.is_speaking(), "playback should still be in progress"
    assert log.is_echo("we have three properties available in nashville right now")


def test_a_barge_in_ends_playback_immediately():
    """Twilio drops the queue on `clear`, so the echo window ends with it."""
    log = speaking_log(seconds=30.0)
    assert log.is_speaking()
    log.notify_cleared()
    assert not log.is_speaking()


def test_nothing_spoken_means_nothing_is_ever_echo():
    log = SpokenLog()
    log.note_audio_sent(8000 * 5)
    assert not log.is_echo("we have three properties available in nashville")


# --- arbitration ------------------------------------------------------------

def test_a_split_question_becomes_one_turn():
    assert merge_utterances(["book me a viewing", "on Thursday"]) == \
        "book me a viewing on Thursday"


def test_a_correction_keeps_both_halves():
    """
    The model resolves "actually, make that Austin" far better than a rule
    here could — what matters is that it is not answered as two questions.
    """
    merged = merge_utterances(["I'm looking in Nashville",
                               "actually, make that Austin"])
    assert "Nashville" in merged and "Austin" in merged


def test_a_repeated_fragment_is_not_stuttered():
    assert merge_utterances(["what properties do you have",
                             "what properties do you have"]) == \
        "what properties do you have"


def test_blank_utterances_are_dropped():
    assert merge_utterances(["", "  ", "hello"]) == "hello"


# --- coalescing -------------------------------------------------------------

class FakeStt:
    """Hands out utterances on a schedule, like the real stream does."""

    def __init__(self, schedule):
        self._schedule = list(schedule)     # (delay_before, text|None)

    async def next_utterance(self, timeout=None):
        if not self._schedule:
            await asyncio.sleep(timeout if timeout is not None else 10)
            raise asyncio.TimeoutError
        delay, text = self._schedule[0]
        if timeout is not None and delay > timeout:
            await asyncio.sleep(timeout)
            self._schedule[0] = (delay - timeout, text)
            raise asyncio.TimeoutError
        await asyncio.sleep(delay)
        self._schedule.pop(0)
        return text


@pytest.mark.asyncio
async def test_a_continuation_is_swept_into_the_same_turn():
    stt = FakeStt([(0.0, "book me a viewing"), (0.15, "on Thursday")])
    assert await collect_turn(stt) == "book me a viewing on Thursday"


@pytest.mark.asyncio
async def test_a_separate_question_is_a_separate_turn():
    """A long gap means they finished; do not swallow the next question."""
    stt = FakeStt([(0.0, "what have you got in Nashville"),
                   (1.0, "and what about Austin")])
    assert await collect_turn(stt) == "what have you got in Nashville"


@pytest.mark.asyncio
async def test_a_rambling_caller_is_still_answered():
    """Continuations must not hold the turn open indefinitely."""
    stt = FakeStt([(0.0, "so")] + [(0.2, f"and another thing {i}") for i in range(20)])
    turn = await asyncio.wait_for(collect_turn(stt), timeout=4.0)
    assert turn.startswith("so and another thing")


@pytest.mark.asyncio
async def test_end_of_stream_returns_none():
    assert await collect_turn(FakeStt([(0.0, None)])) is None


# --- barge-in ---------------------------------------------------------------

class FakeVad:
    def __init__(self, started, text=""):
        self.speech_started = asyncio.Event()
        if started:
            self.speech_started.set()
        self._text = text

    def live_text(self):
        return self._text


def test_voice_activity_alone_does_not_interrupt():
    """An echo trips Deepgram's VAD exactly like a person does."""
    from app.voice.router import _caller_is_interrupting
    assert not _caller_is_interrupting(FakeVad(True, ""), speaking_log())


def test_hearing_ourselves_does_not_interrupt():
    from app.voice.router import _caller_is_interrupting
    stt = FakeVad(True, "we have three properties available in nashville")
    assert not _caller_is_interrupting(stt, speaking_log())


def test_a_real_interruption_does_interrupt():
    from app.voice.router import _caller_is_interrupting
    stt = FakeVad(True, "wait, what about Austin")
    assert _caller_is_interrupting(stt, speaking_log())


def test_silence_does_not_interrupt():
    from app.voice.router import _caller_is_interrupting
    assert not _caller_is_interrupting(FakeVad(False, "anything"), speaking_log())


@pytest.mark.asyncio
async def test_echo_neither_starts_a_turn_nor_rides_into_one():
    """
    Attribution has to run per utterance, before merging. Testing the merged
    result instead dilutes the score with the caller's real words, and the
    assistant's own voice rides into the turn on the back of them:

      Caller: Do you have anything with three bedrooms in Austin? Hello? I
              think there might be a mix up I'm actually Shahir's assistant...
    """
    log = speaking_log(seconds=30.0)
    stt = FakeStt([
        (0.0, "we have three properties available in nashville"),   # echo, first
        (0.1, "do you have anything in austin"),                    # the caller
        (0.1, "starting at four hundred and forty thousand"),       # echo again
    ])

    turn = await collect_turn(stt, log)

    assert turn == "do you have anything in austin", turn
    assert log.suppressed == 2


@pytest.mark.asyncio
async def test_a_turn_of_pure_echo_is_never_answered():
    """The assistant hearing only itself must simply keep listening."""
    log = speaking_log(seconds=30.0)
    stt = FakeStt([(0.0, "we have three properties available in nashville"),
                   (0.1, "starting at four hundred and forty thousand dollars")])

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(collect_turn(stt, log), timeout=1.5)
    assert log.suppressed == 2


@pytest.mark.asyncio
async def test_collect_turn_without_a_log_is_unchanged():
    stt = FakeStt([(0.0, "book me a viewing"), (0.15, "on Thursday")])
    assert await collect_turn(stt) == "book me a viewing on Thursday"
