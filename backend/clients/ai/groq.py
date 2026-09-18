from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from groq import AsyncGroq
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logging_config import get_logger

from .base import BaseAI

settings = get_settings()
log = get_logger(__name__)

DEFAULT_MODEL = "llama-3.1-8b-instant"

# llama-3.1-8b-instant context window. Input + output must fit inside this.
MODEL_CONTEXT_TOKENS = 8192
# Groq free tier throughput ceiling for this model (tokens per minute).
FREE_TIER_TOKENS_PER_MINUTE = 6000
# Groq free tier request ceiling (requests per minute).
FREE_TIER_REQUESTS_PER_MINUTE = 30
# Headroom for the chat template, role markers and estimation error.
TOKEN_ESTIMATE_SAFETY_MARGIN = 256


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


def _messages_tokens(messages: list[dict[str, Any]]) -> int:
    return sum(estimate_tokens(str(m.get("content", ""))) for m in messages)


def input_token_budget(max_output_tokens: int) -> int:
    """Largest prompt we may send, given the reply we have asked for.

    Bounded by both the model context window and the free-tier per-minute
    ceiling, since a single request larger than the TPM limit can never
    succeed no matter how long we wait.
    """
    context_budget = MODEL_CONTEXT_TOKENS - max_output_tokens - TOKEN_ESTIMATE_SAFETY_MARGIN
    throughput_budget = FREE_TIER_TOKENS_PER_MINUTE - max_output_tokens - TOKEN_ESTIMATE_SAFETY_MARGIN
    return max(512, min(context_budget, throughput_budget))


def _is_retryable_groq_error(exc: BaseException) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 429 or status_code is None or status_code >= 500


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Read the server's Retry-After hint from a rate-limit error, if present."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    for header in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        raw = headers.get(header)
        if not raw:
            continue
        try:
            return float(str(raw).rstrip("s"))
        except (TypeError, ValueError):
            continue
    return None


class _TokenBucket:
    """Sliding-window limiter for the free tier's per-minute token and request caps.

    Groq rejects with 429 once either ceiling is crossed. Waiting before the
    call is much cheaper than burning a retry on a guaranteed rejection.
    """

    WINDOW_SECONDS = 60.0

    def __init__(self, tokens_per_minute: int, requests_per_minute: int) -> None:
        self._tokens_per_minute = tokens_per_minute
        self._requests_per_minute = requests_per_minute
        self._events: list[tuple[float, int]] = []
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self.WINDOW_SECONDS
        self._events = [(ts, count) for ts, count in self._events if ts > cutoff]

    async def acquire(self, tokens: int) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._prune(now)
                used_tokens = sum(count for _, count in self._events)
                used_requests = len(self._events)
                token_ok = used_tokens + tokens <= self._tokens_per_minute
                request_ok = used_requests + 1 <= self._requests_per_minute
                if token_ok and request_ok:
                    self._events.append((now, tokens))
                    return
                oldest = self._events[0][0] if self._events else now
                wait_for = max(0.05, self.WINDOW_SECONDS - (now - oldest))
                log.info(
                    "Groq rate limit reached, waiting %.1fs: used_tokens=%d/%d used_requests=%d/%d next=%d",
                    wait_for, used_tokens, self._tokens_per_minute,
                    used_requests, self._requests_per_minute, tokens,
                )
                await asyncio.sleep(wait_for)


class Groq(BaseAI):
    """Groq chat completion client using Groq's native async SDK.

    Free-tier aware: paces requests against the per-minute token and request
    ceilings, and refuses to silently discard prompt content. Callers that have
    more input than fits must split it themselves — see
    ``content_intelligence.transcript_windows``.
    """

    _limiter = _TokenBucket(FREE_TIER_TOKENS_PER_MINUTE, FREE_TIER_REQUESTS_PER_MINUTE)

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

    @staticmethod
    def _fit_messages(messages: list[dict[str, Any]], max_output_tokens: int) -> list[dict[str, Any]]:
        """Trim the prompt to the budget, dropping whole older turns first.

        A single over-budget message is clipped from its *end* and marked, so a
        truncated prompt is visible downstream instead of looking complete.
        """
        budget = input_token_budget(max_output_tokens)
        total = _messages_tokens(messages)
        if total <= budget:
            return messages

        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        available = budget - _messages_tokens(system_msgs)
        if available <= 0:
            log.error("Groq system prompt alone exceeds the input budget of %d tokens", budget)
            return system_msgs[:1]

        kept: list[dict[str, Any]] = []
        used = 0
        for msg in reversed(other_msgs):
            msg_tokens = estimate_tokens(str(msg.get("content", "")))
            if used + msg_tokens <= available:
                kept.insert(0, msg)
                used += msg_tokens
                continue
            remaining = available - used
            content = msg.get("content")
            if remaining > 0 and isinstance(content, str):
                clipped = content[: remaining * 4].rstrip()
                kept.insert(0, {**msg, "content": f"{clipped}\n\n[truncated: prompt exceeded token budget]"})
            break

        log.warning(
            "Groq prompt truncated to fit budget: %d -> %d tokens (budget=%d, messages %d -> %d)",
            total, _messages_tokens(system_msgs + kept), budget, len(messages), len(system_msgs + kept),
        )
        return system_msgs + kept

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        max_output_tokens = int(kwargs.get("max_tokens") or 1024)
        fitted = self._fit_messages(messages, max_output_tokens)
        estimated_input = _messages_tokens(fitted)

        log.info(
            "Groq API call started: mode=chat, model=%s, messages=%d, estimated_input_tokens=%d, max_output_tokens=%d",
            self.model, len(fitted), estimated_input, max_output_tokens,
        )
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception(_is_retryable_groq_error),
            reraise=True,
        ):
            with attempt:
                attempt_number = attempt.retry_state.attempt_number
                await self._limiter.acquire(estimated_input + max_output_tokens)
                log.info("Groq API request hit: mode=chat, model=%s, attempt=%d", self.model, attempt_number)
                try:
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        messages=fitted,
                        stream=False,
                        **kwargs,
                    )
                    content = response.choices[0].message.content or ""
                    finish_reason = getattr(response.choices[0], "finish_reason", None)
                    if finish_reason == "length":
                        log.warning(
                            "Groq response hit the output token cap: model=%s, max_tokens=%d, response_chars=%d",
                            self.model, max_output_tokens, len(content),
                        )
                    log.info(
                        "Groq API call succeeded: mode=chat, model=%s, attempt=%d, response_chars=%d, finish_reason=%s",
                        self.model, attempt_number, len(content), finish_reason,
                    )
                    return content
                except Exception as exc:
                    retry_after = _retry_after_seconds(exc)
                    if retry_after:
                        log.warning(
                            "Groq rate limited, honouring Retry-After=%.1fs: model=%s, attempt=%d",
                            retry_after, self.model, attempt_number,
                        )
                        await asyncio.sleep(retry_after)
                    log.exception(
                        "Groq API call failed: mode=chat, model=%s, attempt=%d",
                        self.model, attempt_number,
                    )
                    raise
        raise RuntimeError("Unreachable")

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        max_output_tokens = int(kwargs.get("max_tokens") or 1024)
        fitted = self._fit_messages(messages, max_output_tokens)
        await self._limiter.acquire(_messages_tokens(fitted) + max_output_tokens)

        log.info("Groq API call started: mode=stream, model=%s, messages=%d", self.model, len(fitted))
        payload = {"model": self.model, "messages": fitted, "stream": True, **kwargs}
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
