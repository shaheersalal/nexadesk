"""
Rule-based lead scoring from conversation signals.
Each rule checks the conversation turn and returns a score delta.
Accumulated score is stored on the lead record in Supabase.
"""
from dataclasses import dataclass


@dataclass
class ScoringEvent:
    rule: str
    delta: int
    triggered_by: str  # the message text that triggered it


SCORING_RULES: dict[str, int] = {
    "shared_name": 10,
    "shared_phone": 15,
    "shared_email": 15,
    "asked_price": 20,
    "asked_availability": 15,
    "requested_showing": 30,
    "mentioned_timeline": 25,
    "mentioned_budget": 20,
    "mortgage_question": 15,
    "specific_property_inquiry": 20,
    "repeat_message": 10,
    "just_browsing": -10,
    "not_interested": -20,
}

# Simple keyword patterns for each rule (lowercased)
_PATTERNS: dict[str, list[str]] = {
    "asked_price": ["how much", "price", "cost", "listing price", "asking price", "what's it listed", "priced at"],
    "asked_availability": ["available", "still on market", "already sold", "when can i", "is it taken"],
    "requested_showing": ["schedule", "showing", "tour", "visit", "see the", "can i come", "appointment", "book a"],
    "mentioned_timeline": ["moving in", "by next", "within", "asap", "end of month", "this year", "next month", "soon"],
    "mentioned_budget": ["budget", "afford", "pre-approved", "pre approval", "looking to spend", "up to $", "around $"],
    "mortgage_question": ["mortgage", "financing", "loan", "down payment", "interest rate", "lender"],
    "specific_property_inquiry": ["bedroom", "bathroom", "sqft", "square feet", "garage", "yard", "pool", "floor plan"],
    "just_browsing": ["just looking", "just browsing", "not ready", "maybe someday", "far away", "not sure yet"],
    "not_interested": ["not interested", "wrong number", "stop calling", "remove me", "unsubscribe"],
}


def score_message(user_message: str, assistant_message: str) -> list[ScoringEvent]:
    """
    Evaluate a conversation turn and return a list of scoring events.
    Checks both the user message and the assistant's response (for
    detecting when the user shares contact info in response to prompts).
    """
    events: list[ScoringEvent] = []
    combined = (user_message + " " + assistant_message).lower()

    for rule, keywords in _PATTERNS.items():
        for kw in keywords:
            if kw in combined:
                events.append(ScoringEvent(
                    rule=rule,
                    delta=SCORING_RULES[rule],
                    triggered_by=kw,
                ))
                break  # one event per rule per turn

    # Contact info detection (simple regex)
    import re
    if re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", user_message):
        events.append(ScoringEvent(rule="shared_phone", delta=SCORING_RULES["shared_phone"], triggered_by="phone number"))
    if re.search(r"\b[\w.+-]+@[\w-]+\.\w{2,}\b", user_message):
        events.append(ScoringEvent(rule="shared_email", delta=SCORING_RULES["shared_email"], triggered_by="email address"))
    if _has_name(user_message):
        events.append(ScoringEvent(rule="shared_name", delta=SCORING_RULES["shared_name"], triggered_by="name"))

    return events


def compute_total_delta(events: list[ScoringEvent]) -> int:
    return sum(e.delta for e in events)


def _has_name(text: str) -> bool:
    """Very loose heuristic: user said 'my name is X' or 'I am X' or 'I'm X'."""
    import re
    return bool(re.search(r"\bmy name(?:\s+is)?\s+\w+|\bi(?:'m| am)\s+[A-Z][a-z]+", text))
