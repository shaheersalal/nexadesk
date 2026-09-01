"""
Deciding whose words are whose, and how many of them make one turn.

The pipeline listens for the whole call, including while the assistant is
speaking, which is what stops a caller's words being missed. Two problems fall
out of that, and this module holds both answers.

**Attribution.** If the line echoes — and it will, on speakerphone, or any
handset whose own cancellation is weak — the assistant hears itself. Deepgram
transcribes it as though the caller said it, so the assistant answers its own
sentence and its own voice activity reads as an interruption, stopping it
mid-word. `SpokenLog` keeps what we just said and recognises it coming back.

**Arbitration.** Deepgram delivers utterances, not thoughts. One question often
arrives as two ("book me a viewing" … "on Thursday"), and a caller who changes
their mind mid-sentence produces two utterances that must not become two
answers. `merge_utterances` joins what belongs together.

Neither is a transcription problem, so neither lives in stt_stream.py: that
module's job ends at turning audio into text.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# How long spoken text stays worth comparing against. Generous, because the
# window check below is what actually bounds it.
RETENTION_SECONDS = 20.0

# Echo arrives while we are speaking, or just after — Twilio buffers our audio,
# and the round trip through the carrier adds more. Outside this window the
# caller is talking about something we said a while ago, and repeating us is
# then a real thing to answer, not an echo to drop.
ECHO_TAIL_SECONDS = 2.5

# Fraction of the utterance's words that must be found, in order, in what we
# just said. Below this it is the caller, even if they picked up our phrasing.
ECHO_MATCH_RATIO = 0.62

# Short utterances are dangerous to discard: a caller's "yes" while the
# assistant is still talking is the most meaningful word in the call. They are
# only dropped on a verbatim run inside what we just said.
ECHO_MIN_WORDS = 4

logger = logging.getLogger("nexadesk.voice.turns")

# A thought often arrives as more than one utterance — "book me a viewing",
# then "on Thursday". Answering each separately produces two replies to one
# question, and the first is answered without the half that gave it meaning.
COALESCE_WINDOW = 0.4
# ...but never hold a turn longer than this in total, however much the caller
# keeps adding, or a talkative caller is never answered at all.
COALESCE_MAX = 1.5

_WORD = re.compile(r"[a-z0-9']+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


@dataclass
class _Spoken:
    at: float
    words: list[str]


@dataclass
class SpokenLog:
    """
    What the assistant has said recently, and whether a transcript is it.

    Content is the discriminator rather than timing or signal level, which is
    what makes this robust: Twilio buffers playback, so we do not know when a
    given clause actually reached the caller, and echo return loss varies by
    handset. What does not vary is that the words coming back are our own.
    """

    _recent: list[_Spoken] = field(default_factory=list)
    _speaking_until: float = 0.0
    suppressed: int = 0

    # -- recording ---------------------------------------------------------
    def note_spoken(self, text: str) -> None:
        """Record text handed to synthesis."""
        words = _words(text)
        if words:
            self._recent.append(_Spoken(time.monotonic(), words))
            self._prune()

    def mark_audio_sent(self) -> None:
        """Called as each audio chunk goes out, to track when we were speaking."""
        self._speaking_until = time.monotonic()

    def is_speaking(self) -> bool:
        return time.monotonic() - self._speaking_until < 0.4

    def _prune(self) -> None:
        cutoff = time.monotonic() - RETENTION_SECONDS
        self._recent = [s for s in self._recent if s.at >= cutoff]

    # -- recognition -------------------------------------------------------
    def echo_score(self, text: str, *, now: float | None = None) -> float:
        """
        How much of `text` is the assistant's own recent speech, 0.0 to 1.0.

        Zero when we were not speaking near enough in time for an echo to be
        possible, so a caller quoting us later is still heard.
        """
        now = time.monotonic() if now is None else now
        if now - self._speaking_until > ECHO_TAIL_SECONDS:
            return 0.0

        heard = _words(text)
        if not heard:
            return 0.0

        self._prune()
        spoken: list[str] = []
        for chunk in self._recent:
            spoken.extend(chunk.words)
        if not spoken:
            return 0.0

        # Ratio of the heard words that line up, in order, with what we said.
        # Asymmetric on purpose: the echo is a fragment of a longer reply, so
        # comparing the two as equals would score a true echo far too low.
        matcher = SequenceMatcher(None, heard, spoken, autojunk=False)
        matched = sum(block.size for block in matcher.get_matching_blocks())
        ratio = matched / len(heard)

        if len(heard) < ECHO_MIN_WORDS:
            # Only a verbatim run counts, so a bare "yes" is never dropped as
            # echo unless we demonstrably just said exactly that.
            longest = matcher.find_longest_match(0, len(heard), 0, len(spoken))
            return 1.0 if longest.size == len(heard) else 0.0
        return ratio

    def is_echo(self, text: str) -> bool:
        return self.echo_score(text) >= ECHO_MATCH_RATIO


def merge_utterances(parts: list[str]) -> str:
    """
    Join utterances that belong to one turn.

    Merged rather than de-duplicated or superseded: when a caller corrects
    themselves — "in Nashville" … "actually, make that Austin" — both halves
    matter, and the model resolves the correction far better than a rule here
    could. What this prevents is the two halves becoming two separate answers.
    """
    seen: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Deepgram sometimes re-sends a finalised fragment as the head of the
        # next utterance; joining those verbatim reads as a stutter.
        if seen and (part == seen[-1] or part in seen[-1]):
            continue
        seen.append(part)
    return " ".join(seen).strip()


async def collect_turn(stt) -> str | None:
    """
    Gather one turn's worth of speech from the transcription stream.

    Blocks for the first utterance, then briefly holds the door open for its
    continuation. Anything the caller said while the previous reply was still
    playing is already queued and gets swept up here, so a turn is answered
    once, with everything in it — which is the whole point of listening through
    the assistant's own speech.

    Returns None when the stream is finished. Propagates asyncio.TimeoutError
    from the initial wait, which is the caller falling silent for good.
    """
    first = await stt.next_utterance()
    if first is None:
        return None

    parts = [first]
    deadline = time.monotonic() + COALESCE_MAX
    while True:
        window = min(COALESCE_WINDOW, deadline - time.monotonic())
        if window <= 0:
            break
        try:
            nxt = await stt.next_utterance(timeout=window)
        except asyncio.TimeoutError:
            break
        if nxt is None:
            break
        parts.append(nxt)

    if len(parts) > 1:
        logger.info("Coalesced %d utterances into one turn", len(parts))
    return merge_utterances(parts)
