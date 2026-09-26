from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from groq import AsyncGroq
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logging_config import get_logger
from usage.context import check_budget
from usage.recorder import record_llm_call

from .base import BaseAI

settings = get_settings()
log = get_logger(__name__)

# llama-3.1-8b-instant and llama-3.3-70b-versatile were decommissioned on
# 2026-08-16 and moved to Enterprise-only, so neither is a usable default.
DEFAULT_MODEL = "openai/gpt-oss-20b"


@dataclass(frozen=True)
class ModelProfile:
    """Per-model limits. Free-tier ceilings differ by model, and a reasoning
    model spends part of its output budget on tokens it never returns."""

    context_tokens: int
    tokens_per_minute: int
    requests_per_minute: int
    reasoning: bool = False


# Unknown models get conservative limits rather than optimistic ones, so a model
# swap degrades into slower calls instead of silent truncation.
FALLBACK_PROFILE = ModelProfile(context_tokens=8192, tokens_per_minute=6000, requests_per_minute=30)

MODEL_PROFILES: dict[str, ModelProfile] = {
    # Free-tier ceilings. The developer tier raises TPM to 250K at the same
    # per-token price, which is the single biggest throughput lever here.
    "openai/gpt-oss-20b": ModelProfile(131072, 8000, 30, reasoning=True),
    "openai/gpt-oss-120b": ModelProfile(131072, 8000, 30, reasoning=True),
    "qwen/qwen3.6-27b": ModelProfile(131072, 8000, 30),
}

# A reasoning model emits hidden reasoning tokens before any content. Below this
# ceiling the budget is consumed entirely by reasoning and the reply comes back
# empty with finish_reason="length".
MIN_REASONING_OUTPUT_TOKENS = 2048

# Reasoning effort asked of a reasoning model. At the default ("medium") a model
# like openai/gpt-oss-20b spends its whole output budget thinking and returns
# empty content for a long extraction prompt, which silently emptied highlight
# detection. "low" leaves the budget for the answer and is ample for the
# structured JSON extraction this codebase asks for.
DEFAULT_REASONING_EFFORT = "low"

# When a reply comes back empty because reasoning consumed the budget, retry
# once with this much more room rather than returning "" to the caller.
EMPTY_REPLY_RETRY_MULTIPLIER = 2

# Headroom for the chat template, role markers and estimation error.
TOKEN_ESTIMATE_SAFETY_MARGIN = 256


def get_profile(model: str | None = None) -> ModelProfile:
    name = (model or getattr(settings, "GROQ_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL).strip()
    return MODEL_PROFILES.get(name, FALLBACK_PROFILE)


def effective_max_tokens(requested: int, model: str | None = None) -> int:
    """Raise the output cap to something a reasoning model can actually use."""
    if get_profile(model).reasoning:
        return max(requested, MIN_REASONING_OUTPUT_TOKENS)
    return requested


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


def _messages_tokens(messages: list[dict[str, Any]]) -> int:
    return sum(estimate_tokens(str(m.get("content", ""))) for m in messages)


def input_token_budget(max_output_tokens: int, model: str | None = None) -> int:
    """Largest prompt we may send, given the reply we have asked for.

    Bounded by both the model context window and the free-tier per-minute
    ceiling, since a single request larger than the TPM limit can never
    succeed no matter how long we wait.
    """
    profile = get_profile(model)
    output = effective_max_tokens(max_output_tokens, model)
    context_budget = profile.context_tokens - output - TOKEN_ESTIMATE_SAFETY_MARGIN
    throughput_budget = profile.tokens_per_minute - output - TOKEN_ESTIMATE_SAFETY_MARGIN
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

    _limiters: dict[str, _TokenBucket] = {}

    @classmethod
    def _limiter_for(cls, model: str) -> _TokenBucket:
        if model not in cls._limiters:
            profile = get_profile(model)
            cls._limiters[model] = _TokenBucket(profile.tokens_per_minute, profile.requests_per_minute)
        return cls._limiters[model]

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0) -> None:
        self.api_key = (api_key or getattr(settings, "GROQ_API_KEY", "") or "").strip()
        self.model = model or getattr(settings, "GROQ_MODEL", DEFAULT_MODEL)
        self.profile = get_profile(self.model)
        if not self.api_key:
            log.warning("Groq API key is missing; Groq-backed steps will fail or fall back.")
        self._client = AsyncGroq(
            api_key=self.api_key,
            timeout=timeout,
        )
        log.info(
            "Groq client initialized: model=%s context=%d tpm=%d reasoning=%s api_key_configured=%s",
            self.model,
            self.profile.context_tokens,
            self.profile.tokens_per_minute,
            self.profile.reasoning,
            bool(self.api_key),
        )

    def input_token_budget(self, max_output_tokens: int) -> int:
        """Largest prompt to send, given the reply we asked for."""
        return input_token_budget(max_output_tokens, self.model)

    def _fit_messages(self, messages: list[dict[str, Any]], max_output_tokens: int) -> list[dict[str, Any]]:
        """Trim the prompt to the budget, dropping whole older turns first.

        A single over-budget message is clipped from its *end* and marked, so a
        truncated prompt is visible downstream instead of looking complete.
        """
        budget = input_token_budget(max_output_tokens, self.model)
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
        """Send one chat completion and return its text.

        Guarantees a non-empty reply or an exception: a reasoning model that
        spends its whole output budget thinking is retried with more room
        instead of handing the caller "" to parse.
        """
        check_budget()
        json_mode = bool(kwargs.pop("json_mode", False))
        # Groq has no schema-enforced output; the schema is Anthropic-only and
        # would be rejected as an unknown parameter here.
        kwargs.pop("json_schema", None)
        content = await self._chat_once(messages, json_mode=json_mode, **kwargs)
        if content.strip():
            return content

        requested = int(kwargs.get("max_tokens") or 1024)
        retry_tokens = effective_max_tokens(requested, self.model) * EMPTY_REPLY_RETRY_MULTIPLIER
        log.warning(
            "Groq returned empty content; retrying with max_tokens=%d: model=%s",
            retry_tokens, self.model,
        )
        retry_kwargs = dict(kwargs)
        retry_kwargs["max_tokens"] = retry_tokens
        content = await self._chat_once(messages, json_mode=json_mode, **retry_kwargs)
        if not content.strip():
            raise RuntimeError(
                f"Groq model {self.model} returned no content even with "
                f"max_tokens={retry_tokens}. Use a non-reasoning model or lower reasoning_effort."
            )
        return content

    async def _chat_once(self, messages: list[dict[str, Any]], json_mode: bool = False, **kwargs: Any) -> str:
        requested = int(kwargs.get("max_tokens") or 1024)
        max_output_tokens = effective_max_tokens(requested, self.model)
        if max_output_tokens != requested:
            log.info(
                "Raised max_tokens %d -> %d for reasoning model %s; a smaller budget is "
                "consumed by reasoning and returns empty content",
                requested, max_output_tokens, self.model,
            )
        kwargs["max_tokens"] = max_output_tokens
        # A reasoning model left at its default effort thinks until the budget is
        # gone and returns nothing. Callers may override per request.
        if self.profile.reasoning:
            kwargs.setdefault("reasoning_effort", DEFAULT_REASONING_EFFORT)
        if json_mode:
            kwargs.setdefault("response_format", {"type": "json_object"})
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
                await self._limiter_for(self.model).acquire(estimated_input + max_output_tokens)
                log.info("Groq API request hit: mode=chat, model=%s, attempt=%d", self.model, attempt_number)
                try:
                    started = time.monotonic()
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        messages=fitted,
                        stream=False,
                        **kwargs,
                    )
                    usage = getattr(response, "usage", None)
                    await record_llm_call(
                        "groq", self.model,
                        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                        effort=kwargs.get("reasoning_effort"),
                        latency_ms=int((time.monotonic() - started) * 1000),
                    )
                    content = response.choices[0].message.content or ""
                    finish_reason = getattr(response.choices[0], "finish_reason", None)
                    if finish_reason == "length" and not content:
                        log.error(
                            "Groq returned no content: model=%s spent all %d output token(s) before "
                            "emitting any. Raise max_tokens or use a non-reasoning model.",
                            self.model, max_output_tokens,
                        )
                    elif finish_reason == "length":
                        log.warning(
                            "Groq response truncated at the output token cap: model=%s, max_tokens=%d, chars=%d",
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
        max_output_tokens = effective_max_tokens(int(kwargs.get("max_tokens") or 1024), self.model)
        kwargs["max_tokens"] = max_output_tokens
        if self.profile.reasoning:
            kwargs.setdefault("reasoning_effort", DEFAULT_REASONING_EFFORT)
        fitted = self._fit_messages(messages, max_output_tokens)
        await self._limiter_for(self.model).acquire(_messages_tokens(fitted) + max_output_tokens)

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
