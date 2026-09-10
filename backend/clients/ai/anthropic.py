from typing import Any, AsyncIterator

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import get_settings

from .base import BaseAI

settings = get_settings()


class Anthropic(BaseAI):
    """Anthropic Claude chat completion client with retry and streaming support."""

    BASE_URL = "https://api.anthropic.com/v1"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0) -> None:
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_MODEL
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._headers,
            timeout=timeout,
            http2=True,
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        system, parsed_messages = self._parse_messages(messages)
        payload = self._build_payload(parsed_messages, system=system, stream=False, **kwargs)
        response = await self._request("messages", payload)
        return response["content"][0]["text"]

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        system, parsed_messages = self._parse_messages(messages)
        payload = self._build_payload(parsed_messages, system=system, stream=True, **kwargs)
        async with self._client.stream("POST", "messages", json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    def _parse_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts: list[str] = []
        parsed: list[dict[str, Any]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                parsed.append({"role": msg["role"], "content": msg["content"]})
        return ("\n".join(system_parts) if system_parts else None, parsed)

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        stream: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            "stream": stream,
            **kwargs,
        }
        if system:
            payload["system"] = system
        return payload

    async def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(httpx.HTTPStatusError),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post(path, json=payload)
                response.raise_for_status()
                return response.json()
        raise RuntimeError("Unreachable")  # pragma: no cover

    async def close(self) -> None:
        await self._client.aclose()
