"""Text embeddings for semantic B-roll search.

Optional: with EMBEDDINGS_PROVIDER=none the library ranks by full-text search
alone. With "gemini", asset descriptions and scene queries are embedded so a
scene about "growing revenue" also finds a clip tagged "rising chart".
"""

from __future__ import annotations

import math
from typing import Protocol

import httpx

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
BATCH = 100


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class GeminiEmbedder:
    def __init__(self, api_key: str, model: str) -> None:
        self._key, self._model = api_key, model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for start in range(0, len(texts), BATCH):
                batch = texts[start:start + BATCH]
                response = await client.post(
                    GEMINI_URL.format(model=self._model),
                    headers={"x-goog-api-key": self._key},
                    json={"requests": [
                        {"model": f"models/{self._model}", "content": {"parts": [{"text": text[:2000]}]}} for text in batch
                    ]},
                )
                response.raise_for_status()
                vectors.extend(item["values"] for item in response.json()["embeddings"])
        return vectors


def get_embedder() -> Embedder | None:
    settings = get_settings()
    if settings.EMBEDDINGS_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        return GeminiEmbedder(settings.GEMINI_API_KEY, settings.GEMINI_EMBEDDING_MODEL)
    return None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
