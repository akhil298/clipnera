from __future__ import annotations

from typing import Any, AsyncIterator

from groq import AsyncGroq
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logging_config import get_logger

from .base import BaseAI

settings = get_settings()
log = get_logger(__name__)

DEFAULT_MODEL = "llama-3.1-8b-instant"
MAX_INPUT_TOKENS = 6000


def _estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for English."""
    return len(text) // 4


def _is_retryable_groq_error(exc: BaseException) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 429 or status_code is None or status_code >= 500


def _truncate_messages(messages: list[dict[str, Any]], max_tokens: int) -> list[dict[str, Any]]:
    """Truncate messages to fit within token budget, preserving system message and recent context."""
    if not messages:
        return messages
    
    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]
    
    total_tokens = sum(_estimate_tokens(str(m.get("content", ""))) for m in messages)
    if total_tokens <= max_tokens:
        return messages
    
    # Keep system messages and truncate from the oldest user/assistant messages
    system_tokens = sum(_estimate_tokens(str(m.get("content", ""))) for m in system_msgs)
    available_tokens = max_tokens - system_tokens
    
    if available_tokens <= 0:
        return system_msgs[:1]
    
    truncated = []
    current_tokens = 0
    # Add messages from the end (most recent first)
    for msg in reversed(other_msgs):
        msg_tokens = _estimate_tokens(str(msg.get("content", "")))
        if current_tokens + msg_tokens > available_tokens:
            remaining_tokens = available_tokens - current_tokens
            content = msg.get("content")
            if remaining_tokens > 0 and isinstance(content, str):
                clipped = content[-remaining_tokens * 4:]
                truncated.insert(0, {**msg, "content": clipped})
            break
        truncated.insert(0, msg)
        current_tokens += msg_tokens
    
    return system_msgs + truncated


class Groq(BaseAI):
    """Groq chat completion client using Groq's native async SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0) -> None:
        self.api_key = (api_key or getattr(settings, "GROQ_API_KEY", "") or "").strip()
        self.model = model or getattr(settings, "GROQ_MODEL", DEFAULT_MODEL)
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
        truncated_messages = _truncate_messages(messages, MAX_INPUT_TOKENS)
        if len(truncated_messages) < len(messages):
            log.warning(
                "[GROQ] Truncated messages from %d to %d to fit input token budget=%d",
                len(messages), len(truncated_messages), MAX_INPUT_TOKENS,
            )
        
        estimated_tokens = sum(_estimate_tokens(str(m.get("content", ""))) for m in truncated_messages)
        log.info(
            "Groq API call started: mode=chat, model=%s, messages=%d, estimated_input_tokens=%d",
            self.model, len(truncated_messages), estimated_tokens,
        )
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception(_is_retryable_groq_error),
            reraise=True,
        ):
            with attempt:
                attempt_number = attempt.retry_state.attempt_number
                log.info("Groq API request hit: mode=chat, model=%s, attempt=%d", self.model, attempt_number)
                try:
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        messages=truncated_messages,
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
        truncated_messages = _truncate_messages(messages, MAX_INPUT_TOKENS)
        if len(truncated_messages) < len(messages):
            log.warning(
                "[GROQ] Truncated messages from %d to %d to fit input token budget=%d",
                len(messages), len(truncated_messages), MAX_INPUT_TOKENS,
            )
        
        log.info("Groq API call started: mode=stream, model=%s, messages=%d", self.model, len(truncated_messages))
        payload = {"model": self.model, "messages": truncated_messages, "stream": True, **kwargs}
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
