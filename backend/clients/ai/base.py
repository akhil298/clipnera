from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


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
