"""Still photos for cutaways and photo cards: public domain and CC0 (Openverse, NASA, Wikimedia), and since the owner
widened the rule on 2026-10-24, Pexels and Pixabay stock (free for commercial use, no credit required).

Each source returns ``StockClip`` records with ``duration_s`` 0, so photos and clips share one licence record.
"""

from __future__ import annotations

import asyncio

from broll.sources.base import StockClip, http_client, split_tags
from core.config import get_settings

OPENVERSE_URL = "https://api.openverse.org/v1/images/"
NASA_URL = "https://images-api.nasa.gov/search"
NASA_LICENSE_URL = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
# Openverse licence codes we accept: CC0 and the Public Domain Mark.
OPEN_LICENCES = {"cc0": "cc0", "pdm": "public_domain"}
# Anonymous Openverse use is rate limited (a burst of searches gets 403/429): one search at a time, one retry.
_OPENVERSE_GATE = asyncio.Semaphore(1)
OPENVERSE_RETRY_SECONDS = 4.0
PEXELS_PHOTOS_URL = "https://api.pexels.com/v1/search"
PIXABAY_PHOTOS_URL = "https://pixabay.com/api/"


class OpenversePhotos:
    name = "openverse"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        params = {"q": query, "license": "cc0,pdm", "page_size": min(20, per_page * 2), "mature": "false"}
        async with _OPENVERSE_GATE, http_client() as client:
            response = await client.get(OPENVERSE_URL, params=params)
            if response.status_code in (403, 429):
                await asyncio.sleep(OPENVERSE_RETRY_SECONDS)
                response = await client.get(OPENVERSE_URL, params=params)
            response.raise_for_status()
            out = []
            for r in response.json().get("results") or []:
                code = OPEN_LICENCES.get(str(r.get("license", "")).lower())
                if not code or not r.get("url"):
                    continue
                out.append(StockClip(source="openverse", source_id=str(r.get("id")), source_url=r.get("foreign_landing_url") or r["url"],
                                     download_url=r["url"], title=r.get("title") or query, tags=[t.get("name", "") for t in r.get("tags") or []][:20],
                                     width=int(r.get("width") or 0), height=int(r.get("height") or 0), duration_s=0.0, license_code=code,
                                     license_url=r.get("license_url"), author=r.get("creator"), record=r))
            return out[:per_page]


class NasaPhotos:
    name = "nasa_photos"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        async with http_client() as client:
            response = await client.get(NASA_URL, params={"q": query, "media_type": "image", "page_size": min(50, per_page * 2)})
            response.raise_for_status()
            out = []
            for item in response.json().get("collection", {}).get("items") or []:
                data = (item.get("data") or [{}])[0]
                link = next((l["href"] for l in item.get("links") or [] if l.get("render") == "image"), None)
                if not link:
                    continue
                large = link.replace("~thumb", "~large").replace("~medium", "~large")
                out.append(StockClip(source="nasa", source_id=data.get("nasa_id", ""), source_url=f"https://images.nasa.gov/details/{data.get('nasa_id', '')}",
                                     download_url=large, title=data.get("title") or query, tags=split_tags(",".join(data.get("keywords") or [])),
                                     width=0, height=0, duration_s=0.0, license_code="public_domain", license_url=NASA_LICENSE_URL,
                                     author=data.get("center"), record=data))
                if len(out) >= per_page:
                    break
            return out


class WikimediaPhotos:
    """Wikimedia Commons photos, public domain and CC0 only (most of Commons is share-alike, which we never take)."""

    name = "wikimedia_photos"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        from broll.sources.wikimedia import API_URL, accepted_license

        params = {
            "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": 6, "gsrlimit": min(50, per_page * 5), "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1280, "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist",
        }
        async with http_client() as client:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            out = []
            for page in (response.json().get("query") or {}).get("pages", {}).values():
                info = (page.get("imageinfo") or [{}])[0]
                meta = {k: v.get("value", "") for k, v in (info.get("extmetadata") or {}).items()}
                code = accepted_license(str(meta.get("LicenseShortName", "")))
                if code not in ("cc0", "public_domain") or not str(info.get("mime", "")).startswith("image/"):
                    continue
                title = str(page.get("title", "")).removeprefix("File:").rsplit(".", 1)[0].replace("_", " ")
                out.append(StockClip(source="wikimedia", source_id=str(page.get("pageid")), source_url=str(info.get("descriptionurl") or ""),
                                     download_url=str(info.get("thumburl") or info.get("url", "")), title=title,
                                     tags=split_tags(title.replace(" ", ",")), width=int(info.get("thumbwidth") or info.get("width") or 0),
                                     height=int(info.get("thumbheight") or info.get("height") or 0), duration_s=0.0, license_code=code,
                                     license_url=str(meta.get("LicenseUrl") or "") or None, author=str(meta.get("Artist") or "")[:200] or None,
                                     record={"page": page.get("title"), "license": meta.get("LicenseShortName")}))
            return out[:per_page]


class PexelsPhotos:
    """Pexels photos, portrait first (https://www.pexels.com/api/documentation/#photos-search)."""

    name = "pexels_photos"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        key = get_settings().PEXELS_API_KEY
        if not key:
            return []
        async with http_client() as client:
            response = await client.get(PEXELS_PHOTOS_URL, params={"query": query, "per_page": min(30, per_page), "orientation": "portrait"},
                                        headers={"Authorization": key})
            response.raise_for_status()
            out = []
            for p in response.json().get("photos") or []:
                src = p.get("src") or {}
                url = src.get("large2x") or src.get("large") or src.get("original")
                if not url:
                    continue
                title = str(p.get("alt") or query)
                out.append(StockClip(source="pexels", source_id=str(p.get("id")), source_url=str(p.get("url") or ""), download_url=url,
                                     title=title, tags=split_tags(title.replace(" ", ",")), width=int(p.get("width") or 0),
                                     height=int(p.get("height") or 0), duration_s=0.0, license_code="pexels",
                                     license_url="https://www.pexels.com/license/", author=p.get("photographer"),
                                     author_url=p.get("photographer_url"), record={"id": p.get("id"), "alt": p.get("alt")}))
            return out[:per_page]


class PixabayPhotos:
    """Pixabay photos (https://pixabay.com/api/docs/#api_search_images); downloaded, never hotlinked."""

    name = "pixabay_photos"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        key = get_settings().PIXABAY_API_KEY
        if not key:
            return []
        async with http_client() as client:
            response = await client.get(PIXABAY_PHOTOS_URL, params={"key": key, "q": query[:100], "image_type": "photo",
                                                                     "per_page": max(3, min(50, per_page)), "safesearch": "true"})
            response.raise_for_status()
            out = []
            for h in response.json().get("hits") or []:
                url = h.get("largeImageURL") or h.get("webformatURL")
                if not url:
                    continue
                tags = split_tags(str(h.get("tags") or ""))
                out.append(StockClip(source="pixabay", source_id=str(h.get("id")), source_url=str(h.get("pageURL") or ""), download_url=url,
                                     title=" ".join(tags[:6]) or query, tags=tags, width=int(h.get("imageWidth") or 0),
                                     height=int(h.get("imageHeight") or 0), duration_s=0.0, license_code="pixabay",
                                     license_url="https://pixabay.com/service/license-summary/", author=h.get("user"),
                                     record={"id": h.get("id"), "tags": h.get("tags")}))
            return out[:per_page]

