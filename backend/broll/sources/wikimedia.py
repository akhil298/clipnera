"""Wikimedia Commons videos (MediaWiki API, no key).

Every file carries its own licence. Only licences that allow commercial reuse
without share-alike are taken: CC0, public domain, and CC BY (with attribution
stored). CC BY-SA would bind our users' whole edit to the same licence, and NC
forbids commercial use, so both are skipped.
"""

from __future__ import annotations

import html
import re

from broll.sources.base import StockClip, http_client

API_URL = "https://commons.wikimedia.org/w/api.php"
_TAG = re.compile(r"<[^>]+>")


def accepted_license(short_name: str) -> str | None:
    """Our licence code for a Commons licence name, or None when we must not use it."""
    name = short_name.strip().lower()
    if "nc" in name.split() or "-nc" in name or "sa" in re.split(r"[\s\-]", name):
        return None
    if name in ("cc0", "cc-zero") or name.startswith("cc0"):
        return "cc0"
    if "public domain" in name or name.startswith("pd"):
        return "public_domain"
    if name.startswith("cc by") or name.startswith("cc-by"):
        return "cc_by"
    return None


def _plain(value: str) -> str:
    return html.unescape(_TAG.sub("", value or "")).strip()


def parse(payload: dict) -> list[StockClip]:
    clips: list[StockClip] = []
    for page in (payload.get("query") or {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = {k: v.get("value", "") for k, v in (info.get("extmetadata") or {}).items()}
        code = accepted_license(str(meta.get("LicenseShortName", "")))
        if not code or not str(info.get("mime", "")).startswith(("video/", "application/ogg")):
            continue
        title = re.sub(r"\.\w+$", "", str(page.get("title", "")).removeprefix("File:")).replace("_", " ")
        author = _plain(str(meta.get("Artist", ""))) or None
        description = _plain(str(meta.get("ImageDescription", "")))
        clips.append(StockClip(
            source="wikimedia",
            source_id=str(page.get("pageid")),
            source_url=str(info.get("descriptionurl") or ""),
            download_url=str(info.get("url", "")).split("?")[0],
            title=title,
            tags=[w for w in re.findall(r"[a-z]{3,}", f"{title} {description[:200]}".lower())][:30],
            width=int(info.get("width") or 0),
            height=int(info.get("height") or 0),
            duration_s=float(info.get("duration") or 0),
            license_code=code,
            license_url=str(meta.get("LicenseUrl") or "") or None,
            author=author,
            author_url=None,
            attribution_text=f"{title} by {author or 'unknown'}, {meta.get('LicenseShortName')}, via Wikimedia Commons",
            record={"page": page.get("title"), "license": meta.get("LicenseShortName"), "description": description[:500]},
        ))
    return clips


class WikimediaSource:
    name = "wikimedia"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        params = {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"{query} filetype:video", "gsrnamespace": 6, "gsrlimit": min(50, per_page * 3),
            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|ImageDescription",
        }
        async with http_client() as client:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            return parse(response.json())[:per_page]
