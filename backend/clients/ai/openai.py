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

from .base import BaseAI, ToolCall, ToolReply, ToolResult, ToolSpec, reply_text
from .groq import TOKEN_ESTIMATE_SAFETY_MARGIN, _arguments

settings = get_settings()
log = get_logger(__name__)

# The smallest window among the chat models this client is pointed at.
CONTEXT_TOKENS = 128_000
DEFAULT_MAX_TOKENS = 4096


# Model families that take ``reasoning_effort`` (o-series, gpt-5 and later); their "-chat" variants do not.
_REASONING_MODEL = re.compile(r"^(o\d|gpt-([5-9]|\d{2,}))(?!.*chat)")
# Output tokens added on top of the reply a caller asked for, so a reasoning
# model can think at its effort and still answer instead of returning nothing.
REASONING_ALLOWANCE = {"minimal": 1024, "low": 2048, "medium": 8192, "high": 16384, "xhigh": 32768}


def reasoning_effort(model: str, requested: str | None = None) -> str | None:
    """``requested`` (else OPENAI_REASONING_EFFORT) for a reasoning model; None for any other.

    gpt-4.1 and gpt-4o reject ``reasoning_effort``, so a role's effort is dropped there.
    """
    if not _REASONING_MODEL.match((model or "").strip().lower()):
        return None
    for effort in (requested, getattr(settings, "OPENAI_REASONING_EFFORT", "")):
        effort = (effort or "").strip().lower()
        if effort in REASONING_ALLOWANCE:
            return effort
    return None


# Deployments that take tools with reasoning only on the Responses API (newer GPT models on
# Azure refuse them on chat completions); their tool calls go there from the first refusal on.
_TOOLS_ON_RESPONSES: set[str] = set()


def _refuses_tool_reasoning(exc: httpx.HTTPStatusError) -> bool:
    if exc.response.status_code != 400:
        return False
    try:
        return exc.response.json().get("error", {}).get("param") == "reasoning_effort"
    except ValueError:
        return False


def _input_part(part: dict[str, Any]) -> dict[str, Any]:
    """A chat content part (text or image) as a Responses input part."""
    if part.get("type") == "image_url":
        return {"type": "input_image", "image_url": part["image_url"]["url"]}
    return {"type": "input_text", "text": part.get("text", "")}


def _responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chat-format messages (with tool calls and results) as Responses input items."""
    items: list[dict[str, Any]] = []
    for message in messages:
        role, content = message["role"], message.get("content")
        if role == "tool":
            items.append({"type": "function_call_output", "call_id": message["tool_call_id"], "output": content or ""})
            continue
        if content:
            parts = content if isinstance(content, str) or role == "assistant" else [_input_part(p) for p in content]
            items.append({"type": "message", "role": role, "content": parts})
        items += [{"type": "function_call", "call_id": c["id"], "name": c["function"]["name"],
                   "arguments": c["function"]["arguments"]} for c in message.get("tool_calls") or []]
    return items


def _responses_reply(data: dict[str, Any]) -> ToolReply:
    """A Responses result as a ToolReply whose ``message`` is in chat format, like the chat path's."""
    texts: list[str] = []
    refusal = ""
    raw_calls: list[dict[str, Any]] = []
    for item in data.get("output") or []:
        if item.get("type") == "function_call":
            raw_calls.append({"id": item["call_id"], "type": "function",
                              "function": {"name": item["name"], "arguments": item.get("arguments") or "{}"}})
        elif item.get("type") == "message":
            for part in item.get("content") or []:
                if part.get("type") == "output_text":
                    texts.append(part.get("text") or "")
                elif part.get("type") == "refusal":
                    refusal = part.get("refusal") or ""
    text = "".join(texts)
    return ToolReply(
        text=text or refusal,
        calls=[ToolCall(id=c["id"], name=c["function"]["name"], arguments=_arguments(c["function"]["arguments"]))
               for c in raw_calls],
        message={"role": "assistant", "content": text, **({"tool_calls": raw_calls} if raw_calls else {})},
        truncated=(data.get("incomplete_details") or {}).get("reason") == "max_output_tokens",
        refused=bool(refusal),
    )


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


def _response_format(schema: dict[str, Any] | None) -> dict[str, Any]:
    """Structured outputs when ``schema`` meets their strict rules, else JSON mode.

    Enforced, an enum such as the director's category or layout can only come
    back as one of its values instead of a near miss that is then discarded.
    """
    if schema is None or not _strict_compatible(schema):
        return {"type": "json_object"}
    return {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema, "strict": True}}


def _strict_compatible(schema: Any) -> bool:
    """Whether every object in ``schema`` closes its properties and requires all of them."""
    if isinstance(schema, list):
        return all(_strict_compatible(item) for item in schema)
    if not isinstance(schema, dict):
        return True
    if schema.get("type") == "object":
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties") is not False or set(schema.get("required") or []) != set(properties):
            return False
    return all(_strict_compatible(value) for value in schema.values())


def _function(tool: ToolSpec) -> dict[str, Any]:
    """A tool definition, strict whenever its schema meets the strict rules, so arguments match it exactly."""
    function = {"name": tool.name, "description": tool.description, "parameters": tool.schema}
    if _strict_compatible(tool.schema):
        function["strict"] = True
    return function


def _is_retryable_openai_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


class OpenAI(BaseAI):
    """OpenAI chat completion client with retries, usage recording and tool calling."""

    BASE_URL = _base_url()
    # Reasoning effort for this client's calls; None means OPENAI_REASONING_EFFORT.
    effort: str | None = None

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 120.0,
                 effort: str | None = None) -> None:
        self.api_key = (api_key or settings.OPENAI_API_KEY or "").strip()
        self.model = model or settings.OPENAI_MODEL
        self.effort = effort
        if not self.api_key:
            log.warning("OpenAI API key is missing; OpenAI-backed steps will fail or fall back.")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._headers,
            timeout=timeout,
            http2=True,
        )
        log.debug("OpenAI client initialized: model=%s api_key_configured=%s", self.model, bool(self.api_key))

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
        schema = kwargs.pop("json_schema", None)
        if kwargs.pop("json_mode", False):
            kwargs.setdefault("response_format", _response_format(schema))
        try:
            choice = (await self._create(messages, mode="chat", **kwargs))["choices"][0]
        except httpx.HTTPStatusError as exc:
            # A deployment on an older API version refuses structured outputs;
            # JSON mode with the shape in the prompt still works there.
            if exc.response.status_code != 400 or kwargs.get("response_format", {}).get("type") != "json_schema":
                raise
            log.warning("OpenAI model %s refused a JSON schema; retrying in JSON mode", self.model)
            kwargs["response_format"] = {"type": "json_object"}
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
        if self.model in _TOOLS_ON_RESPONSES:
            return await self._tools_on_responses(messages, tools, max_tokens)
        try:
            response = await self._create(
                messages, mode="tools", max_tokens=max_tokens,
                tools=[{"type": "function", "function": _function(t)} for t in tools],
                tool_choice="auto",
            )
        except httpx.HTTPStatusError as exc:
            if not _refuses_tool_reasoning(exc):
                raise
            log.warning("OpenAI model %s takes tools with reasoning only on the Responses API; using it", self.model)
            _TOOLS_ON_RESPONSES.add(self.model)
            return await self._tools_on_responses(messages, tools, max_tokens)
        choice = response["choices"][0]
        message = choice["message"]
        raw_calls = message.get("tool_calls") or []
        return ToolReply(
            text=message.get("content") or message.get("refusal") or "",
            calls=[ToolCall(id=c["id"], name=c["function"]["name"], arguments=_arguments(c["function"]["arguments"]))
                   for c in raw_calls],
            message={"role": "assistant", "content": message.get("content") or "",
                     **({"tool_calls": raw_calls} if raw_calls else {})},
            truncated=choice.get("finish_reason") == "length",
            refused=bool(message.get("refusal")),
        )

    async def _tools_on_responses(self, messages: list[dict[str, Any]], tools: list[ToolSpec],
                                  max_tokens: int) -> ToolReply:
        """One tool-loop step on the Responses API, statelessly: the history is sent every time."""
        effort = reasoning_effort(self.model, self.effort)
        payload: dict[str, Any] = {
            "model": self.model,
            "input": _responses_input(messages),
            "tools": [{"type": "function", **_function(t)} for t in tools],
            "tool_choice": "auto",
            "max_output_tokens": max_tokens + REASONING_ALLOWANCE.get(effort or "", 0),
            "store": False,
        }
        if effort:
            payload["reasoning"] = {"effort": effort}
        data = await self._send("responses", payload, mode="tools")
        return _responses_reply(data)

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
        if self.temperature is not None:
            kwargs.setdefault("temperature", self.temperature)
        effort = reasoning_effort(self.model, kwargs.pop("reasoning_effort", None) or self.effort)
        if effort:
            # Reasoning models accept only their default sampling.
            kwargs.pop("temperature", None)
            kwargs.pop("top_p", None)
            kwargs["reasoning_effort"] = effort
            max_tokens += REASONING_ALLOWANCE.get(effort, 0)
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
        log.debug(
            "OpenAI API call started: mode=%s, model=%s, messages=%d, max_output_tokens=%d",
            mode, self.model, len(messages), payload["max_completion_tokens"],
        )
        return await self._send("chat/completions", payload, mode=mode)

    async def _send(self, path: str, payload: dict[str, Any], *, mode: str) -> dict[str, Any]:
        """POST ``payload`` to chat completions or responses, with retries and usage recording."""
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception(_is_retryable_openai_error),
            reraise=True,
        ):
            with attempt:
                started = time.monotonic()
                response = await self._client.post(path, json=payload)
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
                    # Chat completions name them prompt/completion; the Responses API input/output.
                    input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
                    output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    response=reply_text(data) if "choices" in data else _responses_reply(data).text,
                    role=self.role,
                )
                log.debug("OpenAI API call succeeded: mode=%s, model=%s, path=%s", mode, self.model, path)
                return data
        raise RuntimeError("Unreachable")  # pragma: no cover

    async def close(self) -> None:
        await self._client.aclose()
        log.debug("OpenAI client closed: model=%s", self.model)
