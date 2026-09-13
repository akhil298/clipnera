from typing import Any, AsyncIterator

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logging_config import get_logger

from .base import BaseAI

settings = get_settings()
log = get_logger(__name__)


class GeminiQuotaExceeded(RuntimeError):
    """Raised after Gemini rejects a request because the configured quota is exhausted."""


class Gemini(BaseAI):
    """Google Gemini chat completion client with retry and streaming support."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._quota_exhausted = False
        if not self.api_key:
            log.warning("Gemini API key is missing; Gemini-backed steps will fail or fall back.")
        log.info("Gemini client initialized: model=%s, timeout=%ss, api_key_configured=%s", self.model, timeout, bool(self.api_key))
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout,
            http2=True,
        )

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        if self._quota_exhausted:
            return ""
        payload = self._build_payload(messages, **kwargs)
        path = f"models/{self.model}:generateContent"
        log.info("Gemini API call started: mode=chat, model=%s, messages=%d", self.model, len(messages))
        try:
            response = await self._request(path, payload)
        except GeminiQuotaExceeded:
            log.warning("Gemini quota exhausted; continuing without Gemini response")
            return ""
        return response["candidates"][0]["content"]["parts"][0]["text"]

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        if self._quota_exhausted:
            return
        payload = self._build_payload(messages, **kwargs)
        path = f"models/{self.model}:streamGenerateContent"
        params = {"alt": "sse"}
        log.info("Gemini API call started: mode=stream, model=%s, messages=%d", self.model, len(messages))
        async with self._client.stream(
            "POST",
            path,
            json=payload,
            params=params,
            headers={"x-goog-api-key": self.api_key},
        ) as response:
            if response.status_code == 429:
                self._quota_exhausted = True
                log.warning("Gemini quota exhausted: model=%s; disabling further requests", self.model)
                return
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    def _build_payload(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        contents = []
        system_parts = []
        for msg in messages:
            role = msg["role"]
            parts = self._build_parts(msg.get("content", ""))
            if role == "system":
                system_parts.extend(parts)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": parts})

        payload = {"contents": contents, **self._with_generation_config(kwargs)}
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        return payload

    @staticmethod
    def _build_parts(content: Any) -> list[dict[str, Any]]:
        if isinstance(content, str):
            return [{"text": content}]

        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append({"text": item.get("text", "")})
            elif item.get("type") == "image_url":
                image_url = item.get("image_url", {}).get("url", "")
                if image_url.startswith("data:"):
                    header, image_data = image_url.split(",", 1)
                    mime_type = header.split(";", 1)[0].removeprefix("data:")
                    parts.append({"inlineData": {"mimeType": mime_type, "data": image_data}})
        return parts or [{"text": ""}]

    @staticmethod
    def _with_generation_config(kwargs: dict[str, Any]) -> dict[str, Any]:
        config = {}
        if "temperature" in kwargs:
            config["temperature"] = kwargs.pop("temperature")
        if "max_tokens" in kwargs:
            config["maxOutputTokens"] = kwargs.pop("max_tokens")
        return {"generationConfig": config} if config else {}

    async def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._quota_exhausted:
            raise GeminiQuotaExceeded("Gemini quota is exhausted for this client")

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception(_retryable_gemini_error),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post(
                    path,
                    json=payload,
                    headers={"x-goog-api-key": self.api_key},
                )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    if response.status_code == 429:
                        self._quota_exhausted = True
                        log.error(
                            "Gemini quota exhausted: model=%s; disabling further requests for this client",
                            self.model,
                        )
                        raise GeminiQuotaExceeded("Gemini quota is exhausted for this client")
                    log.exception(
                        "Gemini API call failed: model=%s, status=%d, response=%s",
                        self.model,
                        response.status_code,
                        response.text[:500],
                    )
                    raise
                log.info("Gemini API call succeeded: model=%s, status=%d", self.model, response.status_code)
                return response.json()
        raise RuntimeError("Unreachable")  # pragma: no cover

    async def close(self) -> None:
        await self._client.aclose()
        log.info("Gemini client closed: model=%s", self.model)


def _retryable_gemini_error(retry_state: Any) -> bool:
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    return isinstance(exception, httpx.HTTPStatusError) and (
        exception.response.status_code >= 500 or exception.response.status_code == 408
    )
