"""What every stock source returns: one downloadable clip with its licence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

# Wikimedia's robot policy turns away clients whose User-Agent gives no way to reach the operator.
USER_AGENT = "Clipnera/1.0 (https://clipnera.d3e8f5t1cqmtz2.amplifyapp.com; video editing, public-domain media)"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@dataclass
class StockClip:
    source: str
    source_id: str
    source_url: str
    download_url: str
    title: str
    tags: list[str]
    width: int
    height: int
    duration_s: float
    license_code: str
    license_url: str | None
    commercial_ok: bool = True
    author: str | None = None
    author_url: str | None = None
    attribution_text: str | None = None
    # The source API's record, kept as licence evidence.
    record: dict[str, Any] = field(default_factory=dict)


class StockSource(Protocol):
    name: str

    async def search(self, query: str, per_page: int) -> list[StockClip]: ...


def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def split_tags(text: str) -> list[str]:
    return [t.strip().lower() for t in text.replace(";", ",").split(",") if t.strip()][:30]


def best_rendition(files: list[dict[str, Any]], max_short_side: int = 1080) -> dict[str, Any] | None:
    """The largest file whose short side is at most ``max_short_side`` (a 4K master costs more and adds nothing)."""
    def short(f: dict[str, Any]) -> int:
        return min(int(f.get("width") or 0), int(f.get("height") or 0))

    fitting = [f for f in files if 0 < short(f) <= max_short_side]
    pool = fitting or [f for f in files if short(f) > 0]
    return max(pool, key=short, default=None) if fitting else min(pool, key=short, default=None)
