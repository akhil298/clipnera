"""Record and replay model calls for evals (TODO 16.2): same request, same reply, no API call.

A cassette is one JSON file per request, named by the hash of (profile, provider, model, messages,
tools), under LLM_CASSETTE_DIR/<profile>/. Recording wraps the real client; replay answers from the
files and fails loudly on a request it has never seen, so an eval can't quietly go live.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator

from core.config import get_settings

from .base import BaseAI, ToolCall, ToolReply, ToolResult, ToolSpec


class MissingCassette(LookupError):
    pass


def _key(profile: str, inner: BaseAI, kind: str, payload: Any) -> str:
    body = json.dumps({"profile": profile, "provider": type(inner).__name__, "model": getattr(inner, "model", ""),
                       "kind": kind, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:24]


class CassetteClient(BaseAI):
    def __init__(self, inner: BaseAI, mode: str, profile: str) -> None:
        self.inner, self.mode, self.profile = inner, mode, profile
        self.role, self.temperature = inner.role, inner.temperature
        self.folder = Path(get_settings().LLM_CASSETTE_DIR) / profile

    def _path(self, kind: str, payload: Any) -> Path:
        return self.folder / f"{_key(self.profile, self.inner, kind, payload)}.json"

    def _load(self, path: Path) -> Any:
        if not path.exists():
            raise MissingCassette(f"No cassette {path.name} for this request; record it first (LLM_MODE=record).")
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        path = self._path("chat", {"messages": messages, **{k: v for k, v in kwargs.items() if k != "json_schema"}})
        if self.mode == "replay":
            return self._load(path)["text"]
        text = await self.inner.chat(messages, **kwargs)
        self._save(path, {"text": text})
        return text

    async def chat_with_tools(self, messages: list[dict[str, Any]], tools: list[ToolSpec], *,
                              max_tokens: int = 4096) -> ToolReply:
        path = self._path("tools", {"messages": messages, "tools": [t.name for t in tools]})
        if self.mode == "replay":
            data = self._load(path)
            return ToolReply(text=data["text"], calls=[ToolCall(**c) for c in data["calls"]], message=data["message"],
                             truncated=data["truncated"], refused=data["refused"])
        reply = await self.inner.chat_with_tools(messages, tools, max_tokens=max_tokens)
        self._save(path, {**asdict(reply), "calls": [asdict(c) for c in reply.calls]})
        return reply

    def tool_results(self, results: list[ToolResult]) -> list[dict[str, Any]]:
        return self.inner.tool_results(results)

    def image_message(self, text: str, jpegs: list[bytes]) -> dict[str, Any]:
        return self.inner.image_message(text, jpegs)

    async def stream_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        raise NotImplementedError("Streaming isn't recorded")

    async def close(self) -> None:
        await self.inner.close()
