"""
Shared regex patterns used by both chat (app/chat/lead_scoring.py) and voice
(app/voice/conversation.py) to detect contact info shared in conversation.
"""
import re

# International-friendly phone matcher: optional leading "+", then a run of
# digits/separators (space, dash, dot, parens) at least 9 chars long overall.
# Matches US (555-123-4567), UAE (+971 50 123 4567, 050 123 4567) and
# Pakistani (+92 300 1234567, 0300-1234567) formats without requiring a
# specific country's grouping convention.
PHONE_REGEX = re.compile(r"\+?\d[\d\-.\s()]{7,17}\d")

EMAIL_REGEX = re.compile(r"\b[\w.+-]+@[\w-]+\.\w{2,}\b")
