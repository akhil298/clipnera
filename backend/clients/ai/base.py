from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
from typing import Any, AsyncIterator


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


class BaseAI(ABC):
    """Abstract base for all AI provider clients."""

    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Send a chat completion request and return the response text."""
        ...

    @abstractmethod
    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        """Stream a chat completion response chunk by chunk."""
        ...

    async def chat_with_tools(self, messages: list[dict[str, Any]], tools: list[ToolSpec], *,
                              max_tokens: int = 4096) -> ToolReply:
        """One step of a tool loop. ``messages`` may mix plain ``system``/``user``/``assistant``
        messages with earlier ``ToolReply.message`` turns and ``tool_results`` from this provider."""
        raise NotImplementedError(f"{type(self).__name__} does not support tool calling")

    def tool_results(self, results: list[ToolResult]) -> list[dict[str, Any]]:
        """The messages that hand ``results`` back to the model, in this provider's format."""
        raise NotImplementedError(f"{type(self).__name__} does not support tool calling")

    @abstractmethod
    async def close(self) -> None:
        """Close underlying HTTP connections."""
        ...

    async def __aenter__(self) -> "BaseAI":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
