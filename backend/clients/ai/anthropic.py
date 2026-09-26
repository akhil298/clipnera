"""Anthropic Claude client, matching the contract the Groq client exposes.

The two providers differ in ways the callers must not have to care about:

* Claude takes the system prompt as a top-level argument rather than a message.
* Sampling controls (``temperature``, ``top_p``) are rejected with a 400 on the
  current models, so they are dropped rather than forwarded.
* JSON reliability comes from a schema the API enforces (``output_config.format``)
  instead of a "return JSON only" instruction, which is why a caller that passes
  ``json_schema`` gets output that cannot be malformed.
* The context window is 1M rather than Groq's 131K, and there is no per-minute
  token ceiling low enough to matter here, so a transcript that Groq must split
  into windows fits this provider in one request.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic
from anthropic import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from core.config import get_settings
from core.logging_config import get_logger
from usage.context import check_budget
from usage.recorder import record_llm_call

from .base import BaseAI

settings = get_settings()
log = get_logger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"

# Per-model context window and the share of it we are willing to fill with one
# prompt. The models all accept 1M input tokens; the cap below is what a single
# request may use, leaving room for the reply and for estimation error.
MODEL_CONTEXT_TOKENS: dict[str, int] = {
    "claude-opus-5-5": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-haiku-4-5": 200_000,
}
FALLBACK_CONTEXT_TOKENS = 200_000

# Headroom for the chat template and for the 4-chars-per-token estimate being
# wrong on timestamped transcript text.
TOKEN_ESTIMATE_SAFETY_MARGIN = 4_000

# A transcript longer than this still gets split, so one request cannot become
# slow enough to trip a gateway timeout, and so the model's attention is not
# spread across an hour of speech when picking a single moment.
MAX_PROMPT_TOKENS = 120_000

# Callers size ``max_tokens`` for the visible reply, as Groq counts it. Claude
# thinks by default and its thinking is billed against the same cap, so a
# 2600-token cap can be spent entirely on thinking and return no text at all.
# The allowance is added on top of what the caller asked for and scales with
# effort: it bounds what a runaway call can cost, while only tokens actually
# generated are billed.
THINKING_TOKEN_ALLOWANCE = 16_000
THINKING_ALLOWANCE_BY_EFFORT: dict[str, int] = {
    "low": 4_000,
    "medium": 8_000,
    "high": THINKING_TOKEN_ALLOWANCE,
    "xhigh": 32_000,
    "max": 64_000,
}


def output_token_cap(requested: int, effort: str = "high") -> int:
    """``max_tokens`` to send: the caller's reply budget plus thinking room."""
    return requested + THINKING_ALLOWANCE_BY_EFFORT.get(effort, THINKING_TOKEN_ALLOWANCE)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


def get_context_tokens(model: str | None = None) -> int:
    name = (model or getattr(settings, "ANTHROPIC_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL).strip()
    return MODEL_CONTEXT_TOKENS.get(name, FALLBACK_CONTEXT_TOKENS)


def input_token_budget(max_output_tokens: int, model: str | None = None) -> int:
    """Largest prompt to send, given the reply we asked for."""
    ceiling = min(get_context_tokens(model), MAX_PROMPT_TOKENS)
    return max(4_096, ceiling - max_output_tokens - TOKEN_ESTIMATE_SAFETY_MARGIN)


# ``output_config.format.schema`` accepts a subset of JSON Schema: numeric range
# keywords are rejected outright with a 400 ("For 'number' type, properties
# maximum, minimum are not supported"), which used to fail the whole call and
# drop the step to its heuristic fallback. They are stripped here and restated
# in the field's description, so the model still sees the intended range while
# the request stays valid. Callers keep one schema constant that works on every
# provider.
_UNSUPPORTED_SCHEMA_KEYWORDS = (
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "minLength", "maxLength", "pattern",
    "minItems", "maxItems", "uniqueItems",
)


def sanitize_schema(node: Any) -> Any:
    """Return ``node`` with keywords the API rejects removed, recursively."""
    if isinstance(node, list):
        return [sanitize_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    cleaned: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in node.items():
        if key in _UNSUPPORTED_SCHEMA_KEYWORDS:
            dropped.append(f"{key}: {value}")
            continue
        cleaned[key] = sanitize_schema(value)

    if dropped:
        # Keep the constraint visible to the model even though the API will not
        # enforce it.
        note = "Constraints: " + ", ".join(dropped) + "."
        existing = cleaned.get("description")
        cleaned["description"] = f"{existing} {note}".strip() if existing else note
    return cleaned


class Anthropic(BaseAI):
    """Claude chat client used interchangeably with ``clients.ai.groq.Groq``."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 600.0,
        effort: str | None = None,
    ) -> None:
        self.api_key = (api_key or getattr(settings, "ANTHROPIC_API_KEY", "") or "").strip()
        self.model = (model or getattr(settings, "ANTHROPIC_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL).strip()
        self.effort = (effort or getattr(settings, "ANTHROPIC_EFFORT", "medium") or "medium").strip()
        self.context_tokens = get_context_tokens(self.model)
        if not self.api_key:
            log.warning("Anthropic API key is missing; Claude-backed steps will fail.")
        self._client = AsyncAnthropic(api_key=self.api_key, timeout=timeout)
        log.info(
            "Anthropic client initialized: model=%s context=%d effort=%s api_key_configured=%s",
            self.model, self.context_tokens, self.effort, bool(self.api_key),
        )

    def input_token_budget(self, max_output_tokens: int) -> int:
        return input_token_budget(max_output_tokens, self.model)

    @staticmethod
    def _split_system(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
        """Claude takes the system prompt out of band, not as a message."""
        system_parts: list[str] = []
        conversation: list[dict[str, Any]] = []
        for message in messages:
            if message.get("role") == "system":
                system_parts.append(str(message.get("content", "")))
            else:
                conversation.append({"role": message["role"], "content": message["content"]})
        return ("\n\n".join(p for p in system_parts if p) or None, conversation)

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Send one request and return its text, or raise.

        Accepts the same keyword arguments as the Groq client so callers can be
        pointed at either provider. ``temperature`` and other sampling controls
        are accepted and discarded, because the current Claude models reject them.
        """
        requested_max_tokens = int(kwargs.pop("max_tokens", None) or 4096)
        json_mode = bool(kwargs.pop("json_mode", False))
        json_schema = kwargs.pop("json_schema", None)
        # Rejected with a 400 on current models; dropped rather than forwarded so
        # a caller written for Groq does not fail here.
        for unsupported in ("temperature", "top_p", "top_k"):
            kwargs.pop(unsupported, None)

        system, conversation = self._split_system(messages)

        budget = check_budget()
        # Near the run's cap, finish on the cheapest thinking rather than stop.
        effort = "low" if budget is not None and budget.tight else self.effort

        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": output_token_cap(requested_max_tokens, effort),
            "messages": conversation,
        }
        if system:
            # The instruction block is identical across every call of a given
            # step, so caching it makes repeat calls cheaper and faster.
            request["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]

        output_config: dict[str, Any] = {"effort": effort}
        if json_schema:
            # The API enforces this: the reply cannot come back malformed or
            # missing a required field, which is the whole reason to prefer
            # Claude for the steps whose output the pipeline parses.
            output_config["format"] = {"type": "json_schema", "schema": sanitize_schema(json_schema)}
        request["output_config"] = output_config
        request.update(kwargs)

        log.info(
            "Anthropic API call started: model=%s, messages=%d, max_output_tokens=%d, schema=%s",
            self.model, len(conversation), request["max_tokens"], bool(json_schema),
        )

        started = time.monotonic()
        try:
            # Streamed so a long reply cannot hit the HTTP timeout; the helper
            # returns the assembled message.
            async with self._client.messages.stream(**request) as stream:
                response = await stream.get_final_message()
        except RateLimitError:
            log.warning("Anthropic rate limited: model=%s", self.model)
            raise
        except AuthenticationError:
            log.error(
                "Anthropic rejected the API key. Check ANTHROPIC_API_KEY, or set "
                "AI_PROVIDER=groq to run on the free tier."
            )
            raise
        except BadRequestError as exc:
            # A billing failure arrives as a 400, so without this it looks like a
            # malformed request and the pipeline quietly falls back to its
            # transcript heuristic -- which reads as "the AI got worse", not
            # "the account is out of credit".
            message = str(exc)
            if "credit balance is too low" in message:
                log.error(
                    "Anthropic account has no credit, so every Claude step will fail. "
                    "Add credits at console.anthropic.com/settings/billing, or set "
                    "AI_PROVIDER=groq to run on the free tier."
                )
            else:
                log.error("Anthropic rejected the request: model=%s %s", self.model, message[:400])
            raise
        except (APIStatusError, APIConnectionError):
            log.exception("Anthropic API call failed: model=%s", self.model)
            raise

        usage = response.usage
        # Recorded before any check below can raise: a refused or truncated
        # reply is still billed.
        await record_llm_call(
            "anthropic", self.model,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            cache_read_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            cache_write_tokens=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
            effort=effort,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise RuntimeError(
                f"Anthropic declined the request: {getattr(details, 'category', 'unknown')}"
            )

        text = "".join(block.text for block in response.content if block.type == "text")
        log.info(
            "Anthropic API call succeeded: model=%s, chars=%d, stop_reason=%s, "
            "input_tokens=%s, output_tokens=%s, cache_read=%s",
            self.model, len(text), response.stop_reason,
            getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None),
            getattr(usage, "cache_read_input_tokens", None),
        )

        truncated = response.stop_reason == "max_tokens"
        if not text.strip():
            cause = " (output cap spent on thinking)" if truncated else ""
            raise RuntimeError(f"Anthropic model {self.model} returned no text content{cause}")

        if truncated:
            # A schema constrains the shape, not the length: a reply cut off at
            # the cap is still incomplete JSON and parses to nothing downstream.
            log.warning(
                "Anthropic reply hit the output cap at max_tokens=%d; it is truncated",
                request["max_tokens"],
            )

        # A schema-enforced reply is valid JSON by construction, but a caller in
        # json_mode without a schema relies on the prompt; fail loudly here
        # rather than let an unparseable body become an empty result.
        if json_mode and not json_schema:
            try:
                json.loads(text)
            except json.JSONDecodeError:
                log.warning("Anthropic reply in json_mode was not valid JSON: model=%s", self.model)
        return text

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        requested_max_tokens = int(kwargs.pop("max_tokens", None) or 4096)
        kwargs.pop("json_mode", None)
        kwargs.pop("json_schema", None)
        for unsupported in ("temperature", "top_p", "top_k"):
            kwargs.pop(unsupported, None)

        system, conversation = self._split_system(messages)
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": output_token_cap(requested_max_tokens, self.effort),
            "messages": conversation,
            "output_config": {"effort": self.effort},
        }
        if system:
            request["system"] = system
        request.update(kwargs)

        async with self._client.messages.stream(**request) as stream:
            async for chunk in stream.text_stream:
                yield chunk

    async def close(self) -> None:
        await self._client.close()
        log.info("Anthropic client closed: model=%s", self.model)
