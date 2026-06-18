from typing import AsyncGenerator, Optional
import openai

from app.config import get_settings

settings = get_settings()


def _client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)


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
