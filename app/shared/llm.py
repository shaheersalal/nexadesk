from typing import AsyncGenerator, Optional
import openai

from app.config import get_settings

settings = get_settings()


_CLIENT: openai.AsyncOpenAI | None = None


def _client() -> openai.AsyncOpenAI:
    """
    One client per worker, reused for every call.

    This used to construct a fresh AsyncOpenAI per request. Each one builds its
    own httpx connection pool, so every completion paid a full TCP and TLS
    handshake to the API instead of reusing a warm connection — and a chat turn
    makes three or four calls (route, rewrite, generate, extract), so the
    handshakes alone cost close to a second before a single token was produced.

    Safe as a module global: uvicorn runs one event loop per worker, and the
    client is created on first use inside that loop rather than at import.
    """
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY, max_retries=2)
    return _CLIENT


async def complete(
    system: str,
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.3,
    model: Optional[str] = None,
) -> str:
    """Single non-streaming completion. `model` overrides the configured LLM_MODEL."""
    client = _client()
    response = await client.chat.completions.create(
        model=model or settings.LLM_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return response.choices[0].message.content


async def stream(
    system: str,
    messages: list[dict],
    max_tokens: int = 1024,
) -> AsyncGenerator[str, None]:
    """Streaming completion — yields text chunks."""
    client = _client()
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + messages,
        stream=True,
    )
    async for chunk in response:
        text = chunk.choices[0].delta.content
        if text:
            yield text


async def clean_text_with_llm(messy_text: str) -> str:
    """LLM pass for very noisy/garbled documents. Preserves all facts."""
    prompt = (
        "You are a document cleaner. Fix formatting, spelling errors, and garbled text. "
        "Preserve ALL factual content: numbers, names, addresses, prices, dates exactly as they appear. "
        "Return ONLY the cleaned text. No commentary or explanations.\n\n"
        f"TEXT:\n{messy_text[:4000]}"
    )
    return await complete(
        system="You are a precise document cleaning assistant.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.0,
    )
