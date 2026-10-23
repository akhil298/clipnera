"""Still photos for cutaways and photo cards, public domain and CC0 only (the owner's rule for B-roll).

Each source returns ``StockClip`` records with ``duration_s`` 0, so photos and clips share one licence record.
"""

from __future__ import annotations

from broll.sources.base import StockClip, http_client, split_tags

OPENVERSE_URL = "https://api.openverse.org/v1/images/"
NASA_URL = "https://images-api.nasa.gov/search"
NASA_LICENSE_URL = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
# Openverse licence codes we accept: CC0 and the Public Domain Mark.
OPEN_LICENCES = {"cc0": "cc0", "pdm": "public_domain"}


class OpenversePhotos:
    name = "openverse"

    async def search(self, query: str, per_page: int) -> list[StockClip]:
        async with http_client() as client:
            response = await client.get(OPENVERSE_URL, params={"q": query, "license": "cc0,pdm", "page_size": min(20, per_page * 2),
                                                               "mature": "false"})
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
