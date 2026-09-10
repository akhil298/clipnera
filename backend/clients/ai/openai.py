from typing import Any, AsyncIterator

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import get_settings

from .base import BaseAI

settings = get_settings()


class OpenAI(BaseAI):
    """OpenAI chat completion client with retry and streaming support."""

    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._headers,
            timeout=timeout,
            http2=True,
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        payload = self._build_payload(messages, stream=False, **kwargs)
        response = await self._request("chat/completions", payload)
        return response["choices"][0]["message"]["content"]

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        payload = self._build_payload(messages, stream=True, **kwargs)
        async with self._client.stream("POST", "chat/completions", json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    yield line[6:]

    def _build_payload(self, messages: list[dict[str, Any]], stream: bool, **kwargs: Any) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }

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
