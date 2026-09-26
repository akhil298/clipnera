"""Pixabay videos (https://pixabay.com/api/docs/).

Licence: free to use and modify without attribution; no standalone
redistribution, and no commercial use of clips showing recognisable brands.
Off by default (see BROLL_SOURCES) until the API's caching terms are confirmed.
"""

from __future__ import annotations

from broll.sources.base import StockClip, best_rendition, http_client, split_tags
from core.config import get_settings

LICENSE_URL = "https://pixabay.com/service/license-summary/"
SEARCH_URL = "https://pixabay.com/api/videos/"


def parse(payload: dict) -> list[StockClip]:
    clips: list[StockClip] = []
    for hit in payload.get("hits") or []:
        files = [dict(v, name=k) for k, v in (hit.get("videos") or {}).items() if isinstance(v, dict) and v.get("url")]
        rendition = best_rendition(files)
        if not rendition:
            continue
        tags = split_tags(str(hit.get("tags") or ""))
        clips.append(StockClip(
            source="pixabay",
            source_id=str(hit["id"]),
            source_url=str(hit.get("pageURL") or ""),
            download_url=rendition["url"],
            title=" ".join(tags[:6]),
            tags=tags,
            width=int(rendition.get("width") or 0),
            height=int(rendition.get("height") or 0),
            duration_s=float(hit.get("duration") or 0),
            license_code="pixabay",
            license_url=LICENSE_URL,
            author=hit.get("user"),
            author_url=f"https://pixabay.com/users/{hit.get('user')}-{hit.get('user_id')}/" if hit.get("user") else None,
            record=hit,
        ))
    return clips


class PixabaySource:
    name = "pixabay"

    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key if api_key is not None else get_settings().PIXABAY_API_KEY

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        if not self._key:
            raise RuntimeError("PIXABAY_API_KEY is not set")
        async with http_client() as client:
            response = await client.get(
                SEARCH_URL, params={"key": self._key, "q": query, "per_page": max(3, min(200, per_page)), "safesearch": "true"},
            )
            response.raise_for_status()
            return parse(response.json())
