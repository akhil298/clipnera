from __future__ import annotations

from typing import Any, AsyncIterator

from groq import AsyncGroq
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logging_config import get_logger

from .base import BaseAI

settings = get_settings()
log = get_logger(__name__)


class Groq(BaseAI):
    """Groq chat completion client using Groq's native async SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0) -> None:
        self.api_key = (api_key or getattr(settings, "GROQ_API_KEY", "") or "").strip()
        self.model = "openai/gpt-oss-120b"
        if not self.api_key:
            log.warning("Groq API key is missing; Groq-backed steps will fail or fall back.")
        self._client = AsyncGroq(
            api_key=self.api_key,
            timeout=timeout,
        )
        log.info(
            "Groq client initialized: model=%s, timeout=%ss, api_key_configured=%s",
            self.model,
            timeout,
            bool(self.api_key),
        )

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        log.info("Groq API call started: mode=chat, model=%s, messages=%d", self.model, len(messages))
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                attempt_number = attempt.retry_state.attempt_number
                log.info("Groq API request hit: mode=chat, model=%s, attempt=%d", self.model, attempt_number)
                try:
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        stream=False,
                        **kwargs,
                    )
                    content = response.choices[0].message.content or ""
                    log.info(
                        "Groq API call succeeded: mode=chat, model=%s, attempt=%d, response_chars=%d",
                        self.model,
                        attempt_number,
                        len(content),
                    )
                    return content
                except Exception:
                    log.exception(
                        "Groq API call failed: mode=chat, model=%s, attempt=%d",
                        self.model,
                        attempt_number,
                    )
                    raise
        raise RuntimeError("Unreachable")

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        log.info("Groq API call started: mode=stream, model=%s, messages=%d", self.model, len(messages))
        payload = {"model": self.model, "messages": messages, "stream": True, **kwargs}
        chunk_count = 0
        try:
            log.info("Groq API request hit: mode=stream, model=%s", self.model)
            stream = await self._client.chat.completions.create(**payload)
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    chunk_count += 1
                    yield delta.content
            log.info("Groq API call succeeded: mode=stream, model=%s, chunks=%d", self.model, chunk_count)
        except Exception:
            log.exception("Groq API call failed: mode=stream, model=%s, chunks=%d", self.model, chunk_count)
            raise

    async def close(self) -> None:
        await self._client.close()
        log.info("Groq client closed: model=%s", self.model)
