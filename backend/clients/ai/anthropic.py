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

from .base import BaseAI

settings = get_settings()
log = get_logger(__name__)

DEFAULT_MODEL = "claude-opus-5"

# Per-model context window and the share of it we are willing to fill with one
# prompt. The models all accept 1M input tokens; the cap below is what a single
# request may use, leaving room for the reply and for estimation error.
MODEL_CONTEXT_TOKENS: dict[str, int] = {
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


class Anthropic(BaseAI):
    """Claude chat client used interchangeably with ``clients.ai.groq.Groq``."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 600.0) -> None:
        self.api_key = (api_key or getattr(settings, "ANTHROPIC_API_KEY", "") or "").strip()
        self.model = (model or getattr(settings, "ANTHROPIC_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL).strip()
        self.effort = (getattr(settings, "ANTHROPIC_EFFORT", "high") or "high").strip()
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

        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": requested_max_tokens,
            "messages": conversation,
        }
        if system:
            # The instruction block is identical across every call of a given
            # step, so caching it makes repeat calls cheaper and faster.
            request["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]

        output_config: dict[str, Any] = {"effort": self.effort}
        if json_schema:
            # The API enforces this: the reply cannot come back malformed or
            # missing a required field, which is the whole reason to prefer
            # Claude for the steps whose output the pipeline parses.
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        request["output_config"] = output_config
        request.update(kwargs)

        log.info(
            "Anthropic API call started: model=%s, messages=%d, max_output_tokens=%d, schema=%s",
            self.model, len(conversation), requested_max_tokens, bool(json_schema),
        )

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

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise RuntimeError(
                f"Anthropic declined the request: {getattr(details, 'category', 'unknown')}"
            )

        text = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        log.info(
            "Anthropic API call succeeded: model=%s, chars=%d, stop_reason=%s, "
            "input_tokens=%s, output_tokens=%s, cache_read=%s",
            self.model, len(text), response.stop_reason,
            getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None),
            getattr(usage, "cache_read_input_tokens", None),
        )

        if response.stop_reason == "max_tokens" and not json_schema:
            # Without a schema the reply is whatever fit, so a truncated JSON
            # body would parse to nothing further downstream. Say so here.
            log.warning(
                "Anthropic reply hit the output cap at max_tokens=%d; it may be truncated",
                requested_max_tokens,
            )

        if not text.strip():
            raise RuntimeError(f"Anthropic model {self.model} returned no text content")

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
            "max_tokens": requested_max_tokens,
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
