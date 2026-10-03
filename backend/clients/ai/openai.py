"""OpenAI chat client, matching the contract the Groq client exposes.

Talks to ``OPENAI_ENDPOINT`` when one is set, so the same client serves
api.openai.com and any deployment that speaks the chat-completions API.
"""

from __future__ import annotations

import re
import time
from typing import Any, AsyncIterator

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logging_config import get_logger
from usage.context import check_budget
from usage.recorder import record_llm_call

from .base import BaseAI, ToolCall, ToolReply, ToolResult, ToolSpec
from .groq import TOKEN_ESTIMATE_SAFETY_MARGIN, _arguments

settings = get_settings()
log = get_logger(__name__)

# The smallest window among the chat models this client is pointed at.
CONTEXT_TOKENS = 128_000
DEFAULT_MAX_TOKENS = 4096


def input_token_budget(max_output_tokens: int) -> int:
    """Largest prompt we may send, given the reply we have asked for."""
    return CONTEXT_TOKENS - max_output_tokens - TOKEN_ESTIMATE_SAFETY_MARGIN


def _base_url() -> str:
    """The chat-completions root: OPENAI_ENDPOINT, or api.openai.com when none is set.

    An Azure resource or Foundry project URL is accepted as copied from the
    portal; its OpenAI-compatible API lives under ``/openai/v1/``.
    """
    endpoint = (settings.OPENAI_ENDPOINT or "https://api.openai.com/v1").rstrip("/")
    if ".azure.com" in endpoint and not endpoint.endswith("/openai/v1"):
        endpoint += "/openai/v1"
    return endpoint + "/"


def _priced_model(reported: str | None, configured: str) -> str:
    """The model to cost a call at: what the API says served it, without its date stamp.

    An Azure deployment can be named anything, so the configured name alone
    would leave the call unpriced.
    """
    return re.sub(r"-\d{4}-\d{2}-\d{2}$", "", reported or configured)


def _is_retryable_openai_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


class OpenAI(BaseAI):
    """OpenAI chat completion client with retries, usage recording and tool calling."""

    BASE_URL = _base_url()

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 120.0) -> None:
        self.api_key = (api_key or settings.OPENAI_API_KEY or "").strip()
        self.model = model or settings.OPENAI_MODEL
        if not self.api_key:
            log.warning("OpenAI API key is missing; OpenAI-backed steps will fail or fall back.")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._headers,
            timeout=timeout,
            http2=True,
        )
        log.info("OpenAI client initialized: model=%s api_key_configured=%s", self.model, bool(self.api_key))

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def input_token_budget(self, max_output_tokens: int) -> int:
        return input_token_budget(max_output_tokens)

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Send one chat completion and return its text, or raise.

        Accepts the same keyword arguments as the Groq client so callers can be
        pointed at either provider.
        """
        check_budget()
        if kwargs.pop("json_mode", False):
            kwargs.setdefault("response_format", {"type": "json_object"})
        # The pipeline's schemas are written for Claude's enforced output; here,
        # as on Groq, the prompt and JSON mode carry the shape.
        kwargs.pop("json_schema", None)
        choice = (await self._create(messages, mode="chat", **kwargs))["choices"][0]
        content = choice["message"].get("content") or ""
        finish_reason = choice.get("finish_reason")
        if not content.strip():
            raise RuntimeError(f"OpenAI model {self.model} returned no content (finish_reason={finish_reason})")
        if finish_reason == "length":
            log.warning("OpenAI response truncated at the output token cap: model=%s, chars=%d", self.model, len(content))
        return content

    async def chat_with_tools(self, messages: list[dict[str, Any]], tools: list[ToolSpec], *,
                              max_tokens: int = DEFAULT_MAX_TOKENS) -> ToolReply:
        check_budget()
        response = await self._create(
            messages, mode="tools", max_tokens=max_tokens,
            tools=[{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.schema}}
                   for t in tools],
            tool_choice="auto",
        )
        choice = response["choices"][0]
        message = choice["message"]
        raw_calls = message.get("tool_calls") or []
        return ToolReply(
            text=message.get("content") or "",
            calls=[ToolCall(id=c["id"], name=c["function"]["name"], arguments=_arguments(c["function"]["arguments"]))
                   for c in raw_calls],
            message={"role": "assistant", "content": message.get("content") or "",
                     **({"tool_calls": raw_calls} if raw_calls else {})},
            truncated=choice.get("finish_reason") == "length",
        )

    def tool_results(self, results: list[ToolResult]) -> list[dict[str, Any]]:
        return [{"role": "tool", "tool_call_id": r.call_id,
                 "content": f"Error: {r.content}" if r.is_error else r.content} for r in results]

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        payload = self._build_payload(messages, stream=True, **kwargs)
        async with self._client.stream("POST", "chat/completions", json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    yield line[6:]

    def _build_payload(self, messages: list[dict[str, Any]], stream: bool, **kwargs: Any) -> dict[str, Any]:
        # ``max_tokens`` is the callers' name for the cap; current models take it as ``max_completion_tokens``.
        max_tokens = int(kwargs.pop("max_tokens", None) or DEFAULT_MAX_TOKENS)
        return {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "max_completion_tokens": max_tokens,
            **kwargs,
        }

    async def _create(self, messages: list[dict[str, Any]], *, mode: str, **kwargs: Any) -> dict[str, Any]:
        """One completion with retries and usage recording."""
        payload = self._build_payload(messages, stream=False, **kwargs)
        log.info(
            "OpenAI API call started: mode=%s, model=%s, messages=%d, max_output_tokens=%d",
            mode, self.model, len(messages), payload["max_completion_tokens"],
        )
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception(_is_retryable_openai_error),
            reraise=True,
        ):
            with attempt:
                started = time.monotonic()
                response = await self._client.post("chat/completions", json=payload)
                if response.is_error:
                    log.error(
                        "OpenAI API call failed: mode=%s, model=%s, status=%d, body=%s",
                        mode, self.model, response.status_code, response.text[:400],
                    )
                response.raise_for_status()
                data = response.json()
                usage = data.get("usage") or {}
                await record_llm_call(
                    "openai", _priced_model(data.get("model"), self.model),
                    input_tokens=int(usage.get("prompt_tokens") or 0),
                    output_tokens=int(usage.get("completion_tokens") or 0),
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
                log.info(
                    "OpenAI API call succeeded: mode=%s, model=%s, finish_reason=%s",
                    mode, self.model, data["choices"][0].get("finish_reason"),
                )
                return data
        raise RuntimeError("Unreachable")  # pragma: no cover

    async def close(self) -> None:
        await self._client.aclose()
        log.info("OpenAI client closed: model=%s", self.model)
