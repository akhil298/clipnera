"""NASA Image and Video Library (https://images.nasa.gov, no API key).

NASA media is generally not copyrighted in the US and may be used commercially,
but must not imply NASA endorsement, and NASA's insignia are not public domain.
Many NASA videos are press briefings, which make poor B-roll, so talking-head
titles are skipped.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from broll.sources.base import StockClip, http_client

LICENSE_URL = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
SEARCH_URL = "https://images-api.nasa.gov/search"
_TALKING_HEADS = re.compile(r"\b(briefing|conference|interview|panel|remarks|town hall|q&a|webinar|livestream|live stream|live)\b", re.I)


def is_footage(item_data: dict) -> bool:
    text = f"{item_data.get('title', '')} {' '.join(item_data.get('keywords') or [])}"
    return not _TALKING_HEADS.search(text)


def pick_video(asset_urls: list[str]) -> str | None:
    """The ~medium rendition (about 720p); the original master can be many gigabytes."""
    videos = [u for u in asset_urls if u.lower().endswith(".mp4")]
    for suffix in ("~medium.mp4", "~mobile.mp4", "~small.mp4", "~orig.mp4"):
        match = next((u for u in videos if u.endswith(suffix)), None)
        if match:
            return match.replace("http://", "https://", 1).replace(" ", "%20")
    return None


def to_clip(data: dict, download_url: str) -> StockClip:
    nasa_id = str(data.get("nasa_id") or "")
    keywords = [str(k).strip().lower() for k in data.get("keywords") or [] if str(k).strip()]
    return StockClip(
        source="nasa",
        source_id=nasa_id,
        source_url=f"https://images.nasa.gov/details/{quote(nasa_id)}",
        download_url=download_url,
        title=str(data.get("title") or nasa_id),
        tags=[k for k in keywords if k != "nasa"][:30],
        width=0,
        height=0,
        duration_s=0.0,
        license_code="pd_us_gov",
        license_url=LICENSE_URL,
        author=f"NASA {data.get('center') or ''}".strip(),
        attribution_text="Courtesy NASA",
        record=data,
    )


class NasaSource:
    name = "nasa"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        async with http_client() as client:
            response = await client.get(SEARCH_URL, params={"q": query, "media_type": "video", "page_size": min(100, per_page * 3)})
            response.raise_for_status()
            items = response.json().get("collection", {}).get("items") or []
            clips: list[StockClip] = []
            for item in items:
                data = (item.get("data") or [{}])[0]
                if not is_footage(data):
                    continue
                assets = await client.get(item["href"].replace(" ", "%20"))
                if assets.status_code != 200:
                    continue
                url = pick_video(assets.json())
                if url:
                    clips.append(to_clip(data, url))
                if len(clips) >= per_page:
                    break
            return clips
