from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


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

    @abstractmethod
    async def close(self) -> None:
        """Close underlying HTTP connections."""
        ...

    async def __aenter__(self) -> "BaseAI":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
