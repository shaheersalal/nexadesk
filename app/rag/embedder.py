import asyncio
from typing import Sequence

import openai

from app.config import get_settings

settings = get_settings()

BATCH_SIZE = 100  # OpenAI allows up to 2048, but 100 is safe + fast


def _client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=settings.EMBED_API_KEY)


async def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """
    Batch-embed a list of texts. Returns a list of embedding vectors
    in the same order as the input.
    """
    if not texts:
        return []

    client = _client()
    all_embeddings: list[list[float]] = []

    # Process in batches
    for i in range(0, len(texts), BATCH_SIZE):
        batch = list(texts[i : i + BATCH_SIZE])
        response = await client.embeddings.create(
            model=settings.EMBED_MODEL,
            input=batch,
            dimensions=settings.EMBED_DIMENSIONS,
        )
        batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


async def embed_single(text: str) -> list[float]:
    """Embed a single query string."""
    results = await embed_texts([text])
    return results[0]
