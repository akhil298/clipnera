"""Pexels videos (https://www.pexels.com/api/documentation/).

Licence: free to use and modify, no attribution required, but clips may not be
redistributed on other stock platforms; Pexels asks API users to credit it.
Default limits are 200 requests/hour and 20,000/month.
"""

from __future__ import annotations

import re

from broll.sources.base import StockClip, best_rendition, http_client
from core.config import get_settings

LICENSE_URL = "https://www.pexels.com/license/"
SEARCH_URL = "https://api.pexels.com/videos/search"


def _title_from_url(url: str) -> str:
    """Pexels has no description field; the page slug is the clip's own title."""
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"-?\d+$", "", slug)
    return slug.replace("-", " ").strip()


def parse(payload: dict) -> list[StockClip]:
    clips: list[StockClip] = []
    for video in payload.get("videos") or []:
        rendition = best_rendition([f for f in video.get("video_files") or [] if f.get("file_type") == "video/mp4"])
        if not rendition or not rendition.get("link"):
            continue
        title = _title_from_url(str(video.get("url") or ""))
        user = video.get("user") or {}
        clips.append(StockClip(
            source="pexels",
            source_id=str(video["id"]),
            source_url=str(video.get("url") or ""),
            download_url=rendition["link"],
            title=title,
            tags=[w for w in title.lower().split() if len(w) > 2],
            width=int(rendition.get("width") or video.get("width") or 0),
            height=int(rendition.get("height") or video.get("height") or 0),
            duration_s=float(video.get("duration") or 0),
            license_code="pexels",
            license_url=LICENSE_URL,
            author=user.get("name"),
            author_url=user.get("url"),
            attribution_text=f"Video by {user.get('name', 'unknown')} on Pexels",
            record=video,
        ))
    return clips


class PexelsSource:
    name = "pexels"

    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key if api_key is not None else get_settings().PEXELS_API_KEY

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        if not self._key:
            raise RuntimeError("PEXELS_API_KEY is not set")
        async with http_client() as client:
            response = await client.get(
                SEARCH_URL, params={"query": query, "per_page": min(80, per_page)},
                headers={"Authorization": self._key},
            )
            response.raise_for_status()
            return parse(response.json())
