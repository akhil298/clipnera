"""Mixkit stock videos (https://mixkit.co/free-stock-video/), searched from the site: Mixkit has no public API key.

Licence: Mixkit Stock Video Free License: free for commercial and personal projects, no attribution; clips may not
be redistributed as stock on their own. Files are served at 360/720/1080; we take 720 (about 5 MB a clip, 1080 runs
to 50 MB and a reel cutaway gains nothing from it).
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote

from broll.sources.base import StockClip, http_client

LICENSE_URL = "https://mixkit.co/license/#videoFree"
SEARCH_URL = "https://mixkit.co/free-stock-video/discover/{slug}/"
VIDEO_URL = "https://assets.mixkit.co/videos/{id}/{id}-720.mp4"
ITEM = 'data-item-grid--video-player-item-id-value="'


def _slug(query: str) -> str:
    return quote(re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-"))


def _first(pattern: str, text: str) -> str:
    found = re.search(pattern, text)
    return html.unescape(found.group(1)).strip() if found else ""


def parse(page: str) -> list[StockClip]:
    clips: list[StockClip] = []
    seen: set[str] = set()
    for block in page.split(ITEM)[1:]:
        vid = block.split('"', 1)[0]
        if not vid.isdigit() or vid in seen:
            continue
        seen.add(vid)
        title = _first(r'overlay-video-title">\s*([^<]+?)\s*<', block) or _first(r'alt="([^"]+)"', block).rstrip(".")
        about = _first(r'overlay-video-description">\s*([^<]+?)\s*<', block)
        href = _first(r'href="(/free-stock-video/[^"]+)"', block)
        width, height = (int(_first(r'class="item-grid-video-player__thumb"[^>]*width="(\d+)"', block) or 0),
                         int(_first(r'class="item-grid-video-player__thumb"[^>]*height="(\d+)"', block) or 0))
        # The thumbnail keeps the clip's shape; scale it to the 720 rendition we download.
        if width and height:
            width, height = (1280, round(1280 * height / width)) if width >= height else (round(1280 * width / height), 1280)
        words = re.findall(r"[a-z]{3,}", f"{title} {about}".lower())
        clips.append(StockClip(
            source="mixkit",
            source_id=vid,
            source_url=f"https://mixkit.co{href}" if href else "https://mixkit.co/free-stock-video/",
            download_url=VIDEO_URL.format(id=vid),
            title=title or f"Mixkit video {vid}",
            tags=list(dict.fromkeys(words))[:30],
            width=width,
            height=height,
            duration_s=0.0,
            license_code="mixkit",
            license_url=LICENSE_URL,
            record={"id": vid, "title": title, "description": about, "page": href},
        ))
    return clips


class MixkitSource:
    name = "mixkit"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        slug = _slug(query)
        if not slug:
            return []
        async with http_client() as client:
            response = await client.get(SEARCH_URL.format(slug=slug))
            response.raise_for_status()
            return parse(response.text)[:per_page]
