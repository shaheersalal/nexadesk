"""
Redis-backed call session state machine.
Each active call has a CallSession keyed by call_sid.
TTL: 1 hour (auto-expires orphaned sessions).
"""
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

import redis.asyncio as aioredis

SESSION_TTL = 3600  # 1 hour


@dataclass
class CallSession:
    call_sid: str
    company_id: str
    # The number that dialled us, straight off Twilio's `From`. Without this a
    # voice lead has no phone number at all unless the caller reads one out,
    # which makes the lead unactionable — the agency cannot call them back.
    caller_number: Optional[str] = None
    language: str = "en"
    language_confirmed: bool = False  # False until the first turn's audio has been language-detected
    conversation_history: list[dict] = field(default_factory=list)
    lead_data: dict = field(default_factory=dict)
    score: int = 0
    lead_id: Optional[str] = None
    intent: Optional[str] = None  # booking | inquiry | complaint | general
    started_at: Optional[str] = None
    transcript_parts: list[str] = field(default_factory=list)

    def add_turn(self, role: str, content: str) -> None:
        self.conversation_history.append({"role": role, "content": content})
        # Keep last 20 turns in memory
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def to_dict(self) -> dict:
        return asdict(self)


def _key(call_sid: str) -> str:
    return f"call_session:{call_sid}"


async def load_session(call_sid: str, redis: aioredis.Redis) -> Optional[CallSession]:
    raw = await redis.get(_key(call_sid))
    if not raw:
        return None
    data = json.loads(raw)
    return CallSession(**data)


async def save_session(session: CallSession, redis: aioredis.Redis) -> None:
    await redis.setex(_key(session.call_sid), SESSION_TTL, json.dumps(session.to_dict()))


async def delete_session(call_sid: str, redis: aioredis.Redis) -> None:
    await redis.delete(_key(call_sid))


async def create_session(
    call_sid: str,
    company_id: str,
    redis: aioredis.Redis,
    caller_number: Optional[str] = None,
) -> CallSession:
    from datetime import datetime, timezone
    session = CallSession(
        call_sid=call_sid,
        company_id=company_id,
        caller_number=caller_number,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    await save_session(session, redis)
    return session
