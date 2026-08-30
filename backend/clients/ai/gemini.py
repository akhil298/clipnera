from typing import Any, AsyncIterator

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import get_settings

from .base import BaseAI

settings = get_settings()


class Gemini(BaseAI):
    """Google Gemini chat completion client with retry and streaming support."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout,
            http2=True,
        )

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        payload = self._build_payload(messages, **kwargs)
        path = f"/models/{self.model}:generateContent"
        response = await self._request(path, payload)
        return response["candidates"][0]["content"]["parts"][0]["text"]

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        payload = self._build_payload(messages, **kwargs)
        path = f"/models/{self.model}:streamGenerateContent"
        params = {"alt": "sse"}
        async with self._client.stream("POST", path, json=payload, params=params) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    def _build_payload(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else msg["role"]
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        return {"contents": contents, **self._with_generation_config(kwargs)}

    @staticmethod
    def _with_generation_config(kwargs: dict[str, Any]) -> dict[str, Any]:
        config = {}
        if "temperature" in kwargs:
            config["temperature"] = kwargs.pop("temperature")
        if "max_tokens" in kwargs:
            config["maxOutputTokens"] = kwargs.pop("max_tokens")
        return {"generationConfig": config} if config else {}

    async def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        params = {"key": self.api_key}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(httpx.HTTPStatusError),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post(path, json=payload, params=params)
                response.raise_for_status()
                return response.json()
        raise RuntimeError("Unreachable")  # pragma: no cover

    async def close(self) -> None:
        await self._client.aclose()
