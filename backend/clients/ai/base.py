from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import base64
import json
from typing import Any, AsyncIterator, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


def _field(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def reply_text(response: Any) -> str:
    """What a model answered, as one string for the log: its text plus any tool calls.

    Takes an OpenAI-compatible reply (a dict or SDK object with ``choices``)
    or an Anthropic message (``content`` blocks).
    """
    parts: list[str] = []
    choices = _field(response, "choices")
    if choices:
        message = _field(choices[0], "message") or {}
        if _field(message, "content"):
            parts.append(str(_field(message, "content")))
        for call in _field(message, "tool_calls") or []:
            function = _field(call, "function") or {}
            parts.append(f"tool {_field(function, 'name')}({_field(function, 'arguments')})")
    for block in _field(response, "content") or []:
        kind = _field(block, "type")
        if kind == "text":
            parts.append(str(_field(block, "text")))
        elif kind == "tool_use":
            parts.append(f"tool {_field(block, 'name')}({json.dumps(_field(block, 'input'), default=str)})")
    return " ".join(parts)


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call: ``schema`` is the JSON Schema of its input."""

    name: str
    description: str
    schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False
    # JPEGs the tool looked at; the loop sends them to the model right after the results.
    images: tuple[bytes, ...] = ()


@dataclass(frozen=True)
class ToolReply:
    """One model step of a tool loop."""

    text: str
    calls: list[ToolCall] = field(default_factory=list)
    # The assistant turn in the provider's own format. Append it to the
    # conversation unchanged: Claude needs its thinking blocks back on the next step.
    message: dict[str, Any] = field(default_factory=dict)
    # The reply hit the output cap, so any tool call in it may be cut short.
    truncated: bool = False
    # The model declined to answer; ``text`` says why when the provider gives a reason.
    refused: bool = False


class BaseAI(ABC):
    """Abstract base for all AI provider clients."""

    # Set by clients.ai.roles: the role usage is recorded under, and the
    # temperature used when a call gives none (on models that accept one).
    role: str | None = None
    temperature: float | None = None

    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Send a chat completion request and return the response text."""
        ...

    @abstractmethod
    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        """Stream a chat completion response chunk by chunk."""
        ...

    async def chat_json(self, messages: list[dict[str, Any]], schema: type[M], **kwargs: Any) -> M:
        """A reply shaped by ``schema``, validated. The provider enforces the schema where it can:
        close every object (``extra="forbid"``) and require every field for OpenAI's strict mode."""
        text = await self.chat(messages, json_mode=True, json_schema=schema.model_json_schema(), **kwargs)
        return schema.model_validate_json(text)

    async def chat_with_tools(self, messages: list[dict[str, Any]], tools: list[ToolSpec], *,
                              max_tokens: int = 4096) -> ToolReply:
        """One step of a tool loop. ``messages`` may mix plain ``system``/``user``/``assistant``
        messages with earlier ``ToolReply.message`` turns and ``tool_results`` from this provider."""
        raise NotImplementedError(f"{type(self).__name__} does not support tool calling")

    def tool_results(self, results: list[ToolResult]) -> list[dict[str, Any]]:
        """The messages that hand ``results`` back to the model, in this provider's format."""
        raise NotImplementedError(f"{type(self).__name__} does not support tool calling")

    def image_message(self, text: str, jpegs: list[bytes]) -> dict[str, Any]:
        """A user message with ``text`` and JPEG images, in the OpenAI-compatible format."""
        parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
        parts += [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(j).decode()}}
                  for j in jpegs]
        return {"role": "user", "content": parts}

    @abstractmethod
    async def close(self) -> None:
        """Close underlying HTTP connections."""
        ...

    async def __aenter__(self) -> "BaseAI":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
