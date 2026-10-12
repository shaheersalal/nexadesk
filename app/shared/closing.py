"""
The two-minute discipline for Shaheer's own receptionist (ai_studio).

The line exists to qualify a caller and hand them off, not to hold a
conversation: a caller kept talking is a lead that never emails. Instructions
alone do not hold - the model follows whatever canned sentence sits nearest
the reply - so the stage is computed from the clock on a call (or the turn
count in chat) and injected as the LAST instruction in the prompt.

Real-estate tenants are unaffected: only the ai_studio vertical and the voice
turn builder consult this.
"""

import re

CONTACT_EMAIL = "contact@shaheer.dev"
# Said out loud, "contact@shaheer.dev" comes out as noise on an 8 kHz line.
SPOKEN_EMAIL = "contact at shaheer dot dev"

# Call clock, in seconds from the moment Twilio's media stream starts.
SOFT_CLOSE_SECONDS = 75    # start wrapping up
HARD_CLOSE_SECONDS = 105   # give the email and say goodbye, ask nothing
MAX_CALL_SECONDS = 135     # the call is ended for them

# Chat has no clock, so count exchanges instead.
SOFT_CLOSE_TURNS = 6
MAX_CLOSE_TURNS = 8

GOODBYE_LINE = (
    f"Thanks for calling. Email {SPOKEN_EMAIL} with the details and Shaheer will reply. Goodbye."
)

# Spoken instead of a model reply once the hard-close mark passes. The stage
# note asked the model to close and it asked another question instead, so past
# this point the close is not left to it.
CLOSING_LINE = (
    f"That's all I can cover on this call. Email {SPOKEN_EMAIL} with the details "
    "and Shaheer will reply himself. Thanks for calling, goodbye."
)


_WRITTEN_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


def speakable(text: str) -> str:
    """
    Rewrite a written email address the way a person would say it.

    The rules ask the model to say "contact at shaheer dot dev", but it copies
    the written form out of the knowledge base, and how synthesis pronounces
    "@" on an 8 kHz line is a gamble. Done here instead of asked for.
    """
    def _say(match: "re.Match[str]") -> str:
        local = match.group(1).replace(".", " dot ")
        domain = match.group(2).replace(".", " dot ")
        return f"{local} at {domain}"

    return _WRITTEN_EMAIL.sub(_say, text)


def call_stage_note(elapsed_seconds: float) -> str:
    """The closing instruction for where this call is on the 2-minute clock."""
    if elapsed_seconds >= HARD_CLOSE_SECONDS:
        return (
            "\n[The two minutes are up. In ONE sentence: ask them to email "
            f"{SPOKEN_EMAIL} with the details, say Shaheer replies there himself, "
            "thank them and say goodbye. Ask no further questions.]"
        )
    if elapsed_seconds >= SOFT_CLOSE_SECONDS:
        return (
            "\n[Over a minute into a two-minute call. Wrap up now: if you still do "
            "not have their name and what they need, ask for both in one sentence. "
            f"Otherwise ask them to email {SPOKEN_EMAIL} and say goodbye.]"
        )
    return ""


def chat_stage_note(turns: int) -> str:
    """The same discipline for the website chat, counted in exchanges."""
    if turns >= MAX_CLOSE_TURNS:
        return (
            "\n[This chat has run long enough. In one short reply: ask them to email "
            f"{CONTACT_EMAIL} with their details, say Shaheer replies there himself, "
            "and close. Ask no further questions.]"
        )
    if turns >= SOFT_CLOSE_TURNS:
        return (
            "\n[This chat is running long. Wrap up: if you do not have their name and "
            "what they need, ask for both in one short reply. Otherwise point them to "
            f"{CONTACT_EMAIL} and close.]"
        )
    return ""
