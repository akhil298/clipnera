#!/usr/bin/env python3
"""Clipnera asset harvester: collects commercially safe SFX and video-editing assets.

Agent topology (one asyncio loop; blocking yt-dlp work runs on a thread pool):

    SourceAgent  x (source x category) --> candidates queue
    MetadataInspector x N              --> downloads queue   (license gate, optional page check)
    DownloadAgent x N                  --> disk + SQLite     (SHA-256 dedup, audit trail)
    Orchestrator                       : quotas, per-host rate limits, retries, shutdown

Only CC0, public domain (incl. the CC Public Domain Mark), MIT and Apache-2.0 assets
are accepted. Pexels and Pixabay use their own licenses and are opt-in through
--allow-platform-licenses.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Iterable
from urllib import robotparser
from urllib.parse import quote, urlparse

import aiohttp
from bs4 import BeautifulSoup

log = logging.getLogger("harvester")

AUDIO, VIDEO = "audio", "video"
MEDIA_EXTS = {
    AUDIO: frozenset({".wav", ".mp3", ".ogg", ".oga", ".flac", ".aif", ".aiff", ".m4a", ".opus"}),
    VIDEO: frozenset({".mp4", ".webm", ".mov", ".ogv", ".mkv", ".m4v"}),
}
QUEUE_SIZE = 200
GITHUB_REPOS_PER_SEARCH = 10

# Requests per second per host. Every worker shares these budgets, which keeps us
# inside each API's published quota instead of rotating identities around it.
HOST_RPS = {
    "freesound.org": 0.9,          # 60 requests/minute
    "commons.wikimedia.org": 0.5,  # anonymous API clients get 429s well below 2 rps
    "upload.wikimedia.org": 1.0,
    "archive.org": 1.5,
    "api.pexels.com": 0.05,        # 200 requests/hour on a default key
    "pixabay.com": 1.5,            # 100 requests/60 s
    "api.github.com": 0.4,         # search API: 30 requests/minute with a token
}
DEFAULT_RPS = 4.0
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


# ── Categories (A–Z; each maps to a top-level folder) ─────────────────────────

@dataclass(frozen=True)
class Category:
    folder: str
    media: frozenset
    queries: tuple


CATEGORIES = {
    "ambient": Category("Ambient", frozenset({AUDIO}),
                        ("ambience", "room tone", "city ambience", "forest ambience", "rain ambience")),
    "foley": Category("Foley", frozenset({AUDIO}),
                      ("footsteps", "cloth rustle", "door close", "paper", "glass clink")),
    "glitch": Category("Glitch", frozenset({AUDIO, VIDEO}),
                       ("glitch", "digital distortion", "static noise", "vhs")),
    "green_screen": Category("Green Screen", frozenset({VIDEO}), ("green screen", "chroma key")),
    "motion_graphics": Category("Motion Graphics", frozenset({VIDEO}),
                                ("motion graphics", "abstract loop", "animated background", "particles")),
    "overlays": Category("Overlays", frozenset({VIDEO}),
                         ("light leak", "film grain", "dust scratches", "bokeh", "lens flare")),
    "transitions": Category("Transitions", frozenset({AUDIO, VIDEO}),
                            ("transition", "riser", "impact hit", "reverse cymbal")),
    "ui": Category("UI", frozenset({AUDIO}),
                   ("ui click", "button click", "notification", "interface beep", "pop")),
    "whooshes": Category("Whooshes", frozenset({AUDIO}), ("whoosh", "swoosh", "swish", "pass by")),
}


# ── Licensing ────────────────────────────────────────────────────────────────

STRICT_LICENSES = frozenset({"CC0-1.0", "PDM-1.0", "Public-Domain", "MIT", "Apache-2.0"})
PLATFORM_LICENSES = frozenset({"Pexels-License", "Pixabay-License"})
NOTICE_LICENSES = frozenset({"MIT", "Apache-2.0"})  # must ship with their license text

_DISQUALIFIERS = re.compile(
    r"/by[-/]|\bby\b|attribution|noncommercial|\bnc\b|\bnd\b|no.?deriv|share.?alike|\bsa\b"
    r"|sampling|gpl|fair use|all rights reserved",
    re.I,
)
_LICENSE_PATTERNS = (
    (re.compile(r"publicdomain/zero|\bcc[\s-]?0\b|\bcc[\s-]?zero\b|creative commons 0\b", re.I), "CC0-1.0"),
    (re.compile(r"publicdomain/mark|public domain mark", re.I), "PDM-1.0"),
    (re.compile(r"^\s*(public[\s-]domain|pd(-[\w.-]+)?)\s*$", re.I), "Public-Domain"),
    (re.compile(r"^\s*mit(\s+license)?\s*$|opensource\.org/licenses/mit\b", re.I), "MIT"),
    (re.compile(r"^\s*apache(\s+license)?[\s,-]*(version\s*)?2\.0\s*$|apache\.org/licenses/license-2\.0", re.I),
     "Apache-2.0"),
    (re.compile(r"^\s*pexels license\s*$", re.I), "Pexels-License"),
    (re.compile(r"^\s*pixabay (content )?license\s*$", re.I), "Pixabay-License"),
)


def normalize_license(raw: Iterable[str]) -> str | None:
    """Map raw license names/URLs to one canonical id. Any restrictive signal rejects the lot."""
    found = None
    for value in filter(None, (v.strip() for v in raw)):
        if _DISQUALIFIERS.search(value):
            return None
        for pattern, license_id in _LICENSE_PATTERNS:
            if pattern.search(value):
                found = found or license_id
                break
    return found


def license_from_html(html: str) -> str | None:
    """Read the license a human-facing page declares, ignoring site-wide chrome."""
    soup = BeautifulSoup(html, "html.parser")
    for chrome in soup.select("footer, #footer, .footer, nav, header"):
        chrome.decompose()
    signals = [el.get("href", "") for el in soup.select("a[rel~=license], link[rel~=license]")]
    signals += [el.get_text(" ", strip=True) for el in soup.select(".licensetpl_short")]
    signals += [el["href"] for el in soup.select('a[href*="publicdomain"], a[href*="opensource.org/licenses"]')]
    signals = [s for s in signals if s]
    return normalize_license(signals) if signals else None


# ── Helpers ──────────────────────────────────────────────────────────────────

def slugify(text: str, max_len: int = 60) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "-".join(re.findall(r"[a-z0-9]+", ascii_text.lower()))[:max_len].strip("-")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _first(value) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _html_text(fragment: str) -> str:
    return BeautifulSoup(fragment, "html.parser").get_text(" ", strip=True) if fragment else ""


def _strip_media_ext(name: str) -> str:
    path = Path(name)
    return path.stem if path.suffix.lower() in MEDIA_EXTS[AUDIO] | MEDIA_EXTS[VIDEO] else name


def _query_tokens(query: str) -> list[str]:
    stop = {"sound", "sounds", "effect", "effects", "sfx"}
    return [t for t in re.findall(r"[a-z]+", query.lower()) if len(t) >= 3 and t not in stop]


def sha256_file(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def ytdlp_fetch(url: str, workdir: Path, max_bytes: int) -> tuple[Path, str, int]:
    """Blocking yt-dlp download; runs on the thread pool."""
    import yt_dlp

    workdir.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "format": "best[height<=1080]/best",
        "max_filesize": max_bytes,
        "playlist_items": "1",
        "retries": 3,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [p for p in workdir.iterdir() if p.is_file() and not p.name.endswith(".part")]
    if not files:
        raise RuntimeError("yt-dlp produced no file (likely over --max-file-mb)")
    return (files[0], *sha256_file(files[0]))


# ── Data model ───────────────────────────────────────────────────────────────

@dataclass
class Candidate:
    source: str
    source_id: str
    title: str
    category: str
    media_type: str
    download_url: str
    source_page: str
    raw_license: tuple
    author: str = ""
    collection: str = ""          # repo / archive item the file belongs to
    ext: str = ""
    size_hint: int | None = None
    tags: tuple = ()
    restrictions: str = ""        # trademark / personality / non-free flags from the source
    notice_urls: tuple = ()       # LICENSE/NOTICE files that must travel with MIT/Apache assets
    via_ytdlp: bool = False
    license_id: str = ""          # stamped by MetadataInspector

    def __post_init__(self) -> None:
        if not self.ext and not self.via_ytdlp:
            self.ext = Path(urlparse(self.download_url).path).suffix.lower()


@dataclass
class Config:
    dest: Path
    db_path: Path
    sources: tuple
    categories: tuple
    limit_per_category: int
    max_total: int
    per_query: int
    files_per_item: int
    inspect_workers: int
    download_workers: int
    threads: int
    max_bytes: int
    retries: int
    verify_pages: bool
    use_browser: bool
    allow_platform_licenses: bool
    dry_run: bool
    contact: str
    verbose: bool

    @property
    def user_agent(self) -> str:
        return f"ClipneraAssetHarvester/1.0 (+{self.contact})" if self.contact else "ClipneraAssetHarvester/1.0"


# ── Audit ledger (SQLite) ────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    sha256 TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    collection TEXT,
    title TEXT,
    author TEXT,
    category TEXT NOT NULL,
    media_type TEXT NOT NULL,
    license_id TEXT NOT NULL,
    license_raw TEXT NOT NULL,
    license_notice_path TEXT,
    source_page TEXT NOT NULL,
    download_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    tags TEXT,
    downloaded_at TEXT NOT NULL,
    UNIQUE (source, source_id)
);
CREATE TABLE IF NOT EXISTS decisions (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    decision TEXT NOT NULL,          -- accepted | rejected | duplicate | failed
    reason TEXT,
    license_raw TEXT,
    source_page TEXT,
    decided_at TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
);
"""


class Ledger:
    """Provenance for every asset kept, plus why every other candidate was not."""

    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def seen(self, source: str, source_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM assets WHERE source = ? AND source_id = ? "
            "UNION ALL SELECT 1 FROM decisions WHERE source = ? AND source_id = ? AND decision = 'duplicate' "
            "LIMIT 1",
            (source, source_id, source, source_id),
        ).fetchone()
        return row is not None

    def has_hash(self, sha256: str) -> bool:
        return self.conn.execute("SELECT 1 FROM assets WHERE sha256 = ?", (sha256,)).fetchone() is not None

    def record_decision(self, c: Candidate, decision: str, reason: str = "") -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (c.source, c.source_id, decision, reason, json.dumps(c.raw_license), c.source_page, _now()),
            )

    def record_asset(self, c: Candidate, sha256: str, size: int, local_path: Path, notice: str | None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sha256, c.source, c.source_id, c.collection, c.title, c.author, c.category, c.media_type,
                 c.license_id, json.dumps(c.raw_license), notice, c.source_page, c.download_url,
                 str(local_path), size, json.dumps(c.tags), _now()),
            )

    def export(self, path: Path) -> None:
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        rows = [dict(r) for r in cursor.execute("SELECT * FROM assets ORDER BY category, local_path")]
        for row in rows:
            row["license_raw"] = json.loads(row["license_raw"])
            row["tags"] = json.loads(row["tags"] or "[]")
        path.write_text(json.dumps({"generated_at": _now(), "count": len(rows), "assets": rows}, indent=2))


# ── HTTP layer: pacing + retries ─────────────────────────────────────────────

class RateLimiter:
    """Per-host pacing shared by every worker. Slot reservation has no await, so it is atomic."""

    def __init__(self, rates: dict[str, float], default: float):
        self._rates, self._default = rates, default
        self._next: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        now = time.monotonic()
        start = max(now, self._next.get(host, 0.0))
        self._next[host] = start + 1.0 / self._rates.get(host, self._default)
        if start > now:
            await asyncio.sleep(start - now)

    def penalize(self, host: str, seconds: float) -> None:
        self._next[host] = max(self._next.get(host, 0.0), time.monotonic() + seconds)


class HttpError(Exception):
    """Non-retryable HTTP failure. The message never includes query strings (API keys live there)."""


class FileTooLarge(Exception):
    pass


class _Retryable(Exception):
    def __init__(self, status: int, retry_after: float | None):
        super().__init__(f"HTTP {status}")
        self.retry_after = retry_after


class Http:
    def __init__(self, session: aiohttp.ClientSession, limiter: RateLimiter, retries: int):
        self.session, self.limiter, self.retries = session, limiter, retries

    async def _get(self, url: str, consume, **kwargs):
        host = urlparse(url).hostname or ""
        for attempt in range(1, self.retries + 1):
            await self.limiter.wait(host)
            try:
                async with self.session.get(url, **kwargs) as resp:
                    if resp.status in RETRY_STATUS:
                        after = resp.headers.get("Retry-After", "")
                        raise _Retryable(resp.status, float(after) if after.isdigit() else None)
                    if resp.status >= 400:
                        raise HttpError(f"HTTP {resp.status} from {host}{urlparse(url).path}")
                    return await consume(resp)
            except (_Retryable, aiohttp.ClientConnectionError, aiohttp.ClientPayloadError, asyncio.TimeoutError) as exc:
                if attempt == self.retries:
                    raise
                delay = getattr(exc, "retry_after", None) or min(120.0, 5.0 * 2 ** attempt) + random.random()
                log.debug("retry %d/%d %s%s in %.1fs (%s)", attempt, self.retries, host, urlparse(url).path, delay, exc)
                self.limiter.penalize(host, delay)

    async def get_json(self, url: str, params=None, headers=None):
        return await self._get(url, lambda r: r.json(content_type=None), params=params, headers=headers)

    async def get_text(self, url: str, headers=None) -> str:
        return await self._get(url, lambda r: r.text(), headers=headers)

    async def download(self, url: str, dest: Path, max_bytes: int) -> tuple[str, int]:
        """Stream to disk, hashing as we go, so dedup costs no second read."""

        async def consume(resp: aiohttp.ClientResponse) -> tuple[str, int]:
            if resp.content_length and resp.content_length > max_bytes:
                raise FileTooLarge(f"{resp.content_length} bytes")
            digest, size = hashlib.sha256(), 0
            with dest.open("wb") as fh:
                async for chunk in resp.content.iter_chunked(1 << 16):
                    size += len(chunk)
                    if size > max_bytes:
                        raise FileTooLarge(f">{max_bytes} bytes")
                    digest.update(chunk)
                    fh.write(chunk)
            return digest.hexdigest(), size

        return await self._get(url, consume)


# ── Source agents ────────────────────────────────────────────────────────────

class SourceAgent:
    name = ""
    media: frozenset = frozenset()
    key_env = ""
    key_required = True
    platform_licensed = False

    def __init__(self, http: Http, cfg: Config):
        self.http, self.cfg = http, cfg
        self.key = os.environ.get(self.key_env, "") if self.key_env else ""

    def search(self, query: str, media: str, category: str, limit: int) -> AsyncIterator[Candidate]:
        raise NotImplementedError


class FreesoundAgent(SourceAgent):
    """Freesound APIv2, filtered server-side to CC0. Token auth serves HQ MP3 previews;
    original files need OAuth2 and are out of scope."""

    name, media, key_env = "freesound", frozenset({AUDIO}), "FREESOUND_API_KEY"

    async def search(self, query, media, category, limit):
        url = "https://freesound.org/apiv2/search/text/"
        params = {
            "query": query,
            "filter": 'license:"Creative Commons 0"',
            "fields": "id,name,tags,license,username,url,previews",
            "page_size": str(min(limit, 150)),
        }
        headers = {"Authorization": f"Token {self.key}"}
        count = 0
        while url:
            data = await self.http.get_json(url, params=params, headers=headers)
            for sound in data.get("results", []):
                preview = (sound.get("previews") or {}).get("preview-hq-mp3")
                if not preview:
                    continue
                yield Candidate(
                    source=self.name, source_id=str(sound["id"]), title=_strip_media_ext(sound.get("name", "")),
                    category=category, media_type=AUDIO, download_url=preview, source_page=sound.get("url", ""),
                    raw_license=(sound.get("license", ""),), author=sound.get("username", ""), ext=".mp3",
                    tags=tuple(sound.get("tags") or ()),
                )
                count += 1
                if count >= limit:
                    return
            url, params = data.get("next"), None


class WikimediaAgent(SourceAgent):
    """Wikimedia Commons file search with per-file license metadata (extmetadata)."""

    name, media = "wikimedia", frozenset({AUDIO, VIDEO})
    API = "https://commons.wikimedia.org/w/api.php"

    async def search(self, query, media, category, limit):
        params = {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrsearch": f"{query} filetype:{media}", "gsrnamespace": "6",
            "gsrlimit": str(min(limit, 50)),
            "prop": "imageinfo", "iiprop": "url|size|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Restrictions|NonFree",
        }
        count = 0
        while True:
            data = await self.http.get_json(self.API, params=params)
            for page in data.get("query", {}).get("pages", []):
                info = (page.get("imageinfo") or [{}])[0]
                if not info.get("url"):
                    continue
                meta = {k: str(v.get("value", "")) for k, v in (info.get("extmetadata") or {}).items()}
                restrictions = [meta["Restrictions"]] if meta.get("Restrictions") else []
                if meta.get("NonFree", "").lower() == "true":
                    restrictions.append("non-free")
                yield Candidate(
                    source=self.name, source_id=str(page["pageid"]),
                    title=_strip_media_ext(page["title"].split(":", 1)[-1]), category=category, media_type=media,
                    download_url=info["url"], source_page=info.get("descriptionurl", ""),
                    raw_license=(meta.get("LicenseShortName", ""), meta.get("LicenseUrl", "")),
                    author=_html_text(meta.get("Artist", "")), size_hint=info.get("size"),
                    restrictions=", ".join(restrictions),
                )
                count += 1
                if count >= limit:
                    return
            if "continue" not in data:
                return
            params = {**params, **data["continue"]}


class ArchiveAgent(SourceAgent):
    """Internet Archive items marked CC0 / Public Domain Mark. Audio files are fetched
    directly; video items go through yt-dlp, which picks one sensible rendition."""

    name, media = "archive", frozenset({AUDIO, VIDEO})

    async def search(self, query, media, category, limit):
        mediatype = "audio" if media == AUDIO else "movies"
        params = [
            ("q", f'(title:("{query}") OR subject:("{query}")) AND mediatype:{mediatype} '
                  "AND licenseurl:*publicdomain*"),
            ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "licenseurl"), ("fl[]", "creator"),
            ("rows", str(min(limit, 100))), ("page", "1"), ("output", "json"),
        ]
        data = await self.http.get_json("https://archive.org/advancedsearch.php", params=params)
        count = 0
        for doc in data.get("response", {}).get("docs", []):
            ident = doc["identifier"]
            page = f"https://archive.org/details/{ident}"
            if media == VIDEO:
                found = [Candidate(
                    source=self.name, source_id=ident, collection=ident, title=_first(doc.get("title")) or ident,
                    category=category, media_type=VIDEO, download_url=page, source_page=page,
                    raw_license=(_first(doc.get("licenseurl")),), author=_first(doc.get("creator")), via_ytdlp=True,
                )]
            else:
                found = await self._audio_files(ident, category)
            for candidate in found:
                yield candidate
                count += 1
                if count >= limit:
                    return

    async def _audio_files(self, ident: str, category: str) -> list[Candidate]:
        meta = await self.http.get_json(f"https://archive.org/metadata/{ident}")
        info = meta.get("metadata") or {}
        originals = [
            f for f in meta.get("files", [])
            if f.get("source") == "original" and Path(f.get("name", "")).suffix.lower() in MEDIA_EXTS[AUDIO]
        ]
        return [
            Candidate(
                source=self.name, source_id=f"{ident}/{f['name']}", collection=ident,
                title=_first(f.get("title")) or _strip_media_ext(Path(f["name"]).name), category=category,
                media_type=AUDIO, download_url=f"https://archive.org/download/{ident}/{quote(f['name'])}",
                source_page=f"https://archive.org/details/{ident}", raw_license=(_first(info.get("licenseurl")),),
                author=_first(info.get("creator")), size_hint=int(f.get("size") or 0) or None,
            )
            for f in originals[: self.cfg.files_per_item]
        ]


class PexelsAgent(SourceAgent):
    """Pexels videos. Pexels License, not CC0: skipped unless --allow-platform-licenses."""

    name, media, key_env, platform_licensed = "pexels", frozenset({VIDEO}), "PEXELS_API_KEY", True

    async def search(self, query, media, category, limit):
        count, page = 0, 1
        while count < limit:
            data = await self.http.get_json(
                "https://api.pexels.com/videos/search",
                params={"query": query, "per_page": str(min(limit, 80)), "page": str(page)},
                headers={"Authorization": self.key},
            )
            videos = data.get("videos", [])
            for video in videos:
                files = [f for f in video.get("video_files", [])
                         if f.get("file_type") == "video/mp4" and (f.get("height") or 0) <= 1080]
                if not files:
                    continue
                best = max(files, key=lambda f: f.get("height") or 0)
                slug = urlparse(video.get("url", "")).path.rstrip("/").rsplit("/", 1)[-1]
                yield Candidate(
                    source=self.name, source_id=str(video["id"]),
                    title=re.sub(r"-?\d+$", "", slug).replace("-", " ") or f"pexels {video['id']}",
                    category=category, media_type=VIDEO, download_url=best["link"],
                    source_page=video.get("url", ""), raw_license=("Pexels License",),
                    author=(video.get("user") or {}).get("name", ""), ext=".mp4",
                )
                count += 1
                if count >= limit:
                    return
            if not videos or not data.get("next_page"):
                return
            page += 1


class PixabayAgent(SourceAgent):
    """Pixabay videos. Pixabay Content License, not CC0: skipped unless --allow-platform-licenses."""

    name, media, key_env, platform_licensed = "pixabay", frozenset({VIDEO}), "PIXABAY_API_KEY", True

    async def search(self, query, media, category, limit):
        count, page, per_page = 0, 1, max(3, min(limit, 200))
        while count < limit:
            data = await self.http.get_json(
                "https://pixabay.com/api/videos/",
                params={"key": self.key, "q": query, "per_page": str(per_page), "page": str(page),
                        "safesearch": "true"},
            )
            hits = data.get("hits", [])
            for hit in hits:
                renditions = hit.get("videos") or {}
                video = renditions.get("large") or renditions.get("medium") or {}
                if not video.get("url"):
                    continue
                tags = tuple(t.strip() for t in hit.get("tags", "").split(",") if t.strip())
                yield Candidate(
                    source=self.name, source_id=str(hit["id"]), title=tags[0] if tags else f"pixabay {hit['id']}",
                    category=category, media_type=VIDEO, download_url=video["url"],
                    source_page=hit.get("pageURL", ""), raw_license=("Pixabay Content License",),
                    author=hit.get("user", ""), ext=".mp4", tags=tags,
                )
                count += 1
                if count >= limit:
                    return
            if not hits or page * per_page >= data.get("totalHits", 0):
                return
            page += 1


class GitHubAgent(SourceAgent):
    """Public SFX repos under CC0 / MIT / Apache-2.0. Repo search and trees are cached
    across categories; files are matched to a category by name."""

    name, media, key_env, key_required = "github", frozenset({AUDIO}), "GITHUB_TOKEN", False
    LICENSES = ("cc0-1.0", "mit", "apache-2.0")
    REPO_QUERIES = ("sound effects", "sfx pack", "game audio")
    NOTICE_FILE = re.compile(r"^(licen[cs]e|copying|notice)(\.\w+)?$", re.I)
    LFS_POINTER_MAX = 1024

    def __init__(self, http: Http, cfg: Config):
        super().__init__(http, cfg)
        self._repos: list | None = None
        self._repos_lock = asyncio.Lock()
        self._trees: dict[str, asyncio.Future] = {}

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        return headers

    async def _repo_list(self) -> list:
        async with self._repos_lock:
            if self._repos is None:
                repos = {}
                for query in self.REPO_QUERIES:
                    for spdx in self.LICENSES:
                        data = await self.http.get_json(
                            "https://api.github.com/search/repositories",
                            params={"q": f"{query} license:{spdx}", "sort": "stars",
                                    "per_page": str(GITHUB_REPOS_PER_SEARCH)},
                            headers=self._headers(),
                        )
                        repos.update((r["full_name"], r) for r in data.get("items", []))
                self._repos = list(repos.values())
        return self._repos

    async def _tree(self, repo: dict) -> list:
        full = repo["full_name"]
        if full not in self._trees:
            self._trees[full] = asyncio.ensure_future(self.http.get_json(
                f"https://api.github.com/repos/{full}/git/trees/{quote(repo['default_branch'])}",
                params={"recursive": "1"}, headers=self._headers(),
            ))
        return (await self._trees[full]).get("tree", [])

    async def search(self, query, media, category, limit):
        tokens = _query_tokens(query)
        count = 0
        for repo in await self._repo_list():
            full, branch = repo["full_name"], quote(repo["default_branch"])
            spdx = (repo.get("license") or {}).get("spdx_id") or ""
            tree = await self._tree(repo)
            raw = f"https://raw.githubusercontent.com/{full}/{branch}/"
            notices = tuple(raw + quote(e["path"]) for e in tree
                            if e["type"] == "blob" and "/" not in e["path"] and self.NOTICE_FILE.match(e["path"]))
            taken = 0
            for entry in tree:
                path = entry["path"]
                if (entry["type"] != "blob" or Path(path).suffix.lower() not in MEDIA_EXTS[AUDIO]
                        or entry.get("size", 0) < self.LFS_POINTER_MAX
                        or not any(t in path.lower() for t in tokens)):
                    continue
                yield Candidate(
                    source=self.name, source_id=f"{full}/{path}", collection=full, title=Path(path).stem,
                    category=category, media_type=AUDIO, download_url=raw + quote(path),
                    source_page=f"{repo['html_url']}/blob/{branch}/{quote(path)}", raw_license=(spdx,),
                    author=repo["owner"]["login"], size_hint=entry.get("size"), notice_urls=notices,
                )
                taken += 1
                count += 1
                if count >= limit:
                    return
                if taken >= self.cfg.files_per_item:
                    break


SOURCES = {cls.name: cls for cls in (
    ArchiveAgent, FreesoundAgent, GitHubAgent, PexelsAgent, PixabayAgent, WikimediaAgent,
)}


# ── Page verification (aiohttp + BeautifulSoup, Playwright fallback) ─────────

class BrowserRenderer:
    """Headless Chromium for license blocks that only exist after JavaScript runs."""

    def __init__(self, user_agent: str, concurrency: int = 2):
        self.user_agent = user_agent
        self._sem = asyncio.Semaphore(concurrency)
        self._start_lock = asyncio.Lock()
        self._playwright = None
        self._browser = None

    async def html(self, url: str) -> str:
        async with self._start_lock:
            if self._browser is None:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
        async with self._sem:
            page = await self._browser.new_page(user_agent=self.user_agent)
            try:
                await page.goto(url, wait_until="networkidle", timeout=45_000)
                return await page.content()
            finally:
                await page.close()

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            await self._playwright.stop()


class PageVerifier:
    """Second opinion: the human-facing page must declare the same license as the API."""

    def __init__(self, http: Http, renderer: BrowserRenderer | None, user_agent: str):
        self.http, self.renderer, self.user_agent = http, renderer, user_agent
        self._robots: dict[str, robotparser.RobotFileParser] = {}

    async def _allowed(self, url: str) -> bool:
        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            parser = robotparser.RobotFileParser()
            try:
                parser.parse((await self.http.get_text(f"{base}/robots.txt")).splitlines())
            except (HttpError, aiohttp.ClientError, asyncio.TimeoutError):
                parser.parse([])
            self._robots[base] = parser
        return self._robots[base].can_fetch(self.user_agent, url)

    async def page_license(self, url: str) -> str | None:
        if not url or not await self._allowed(url):
            return None
        found = license_from_html(await self.http.get_text(url))
        if found is None and self.renderer:
            await self.http.limiter.wait(urlparse(url).hostname or "")
            found = license_from_html(await self.renderer.html(url))
        return found


# ── Inspector and downloader agents ──────────────────────────────────────────

class MetadataInspector:
    """Gatekeeper: nothing reaches the downloader without an allowed, unrestricted license."""

    VERIFIABLE_SOURCES = frozenset({"archive", "freesound", "wikimedia"})

    def __init__(self, cfg: Config, verifier: PageVerifier | None):
        self.allowed = STRICT_LICENSES | (PLATFORM_LICENSES if cfg.allow_platform_licenses else frozenset())
        self.max_bytes = cfg.max_bytes
        self.verifier = verifier

    async def inspect(self, c: Candidate) -> str | None:
        """Return a rejection reason, or None after stamping c.license_id."""
        if c.restrictions:
            return f"restricted: {c.restrictions}"
        license_id = normalize_license(c.raw_license)
        if license_id is None:
            return f"license not allowed: {'; '.join(filter(None, c.raw_license)) or 'missing'}"
        if license_id not in self.allowed:
            return f"{license_id} requires --allow-platform-licenses"
        if license_id in NOTICE_LICENSES and not c.notice_urls:
            return f"{license_id} asset has no license file to retain"
        if not c.via_ytdlp and c.ext not in MEDIA_EXTS[c.media_type]:
            return f"unsupported file type {c.ext or '(none)'}"
        if c.size_hint and c.size_hint > self.max_bytes:
            return "exceeds --max-file-mb"
        if self.verifier and c.source in self.VERIFIABLE_SOURCES:
            on_page = await self.verifier.page_license(c.source_page)
            if on_page != license_id:
                return f"source page shows {on_page or 'no readable license'}, metadata says {license_id}"
        c.license_id = license_id
        return None


class DownloadAgent:
    """Downloads, dedupes by SHA-256, files into <Category>/<A-Z>/ and records provenance."""

    def __init__(self, cfg: Config, http: Http, ledger: Ledger, executor: ThreadPoolExecutor):
        self.dest, self.max_bytes = cfg.dest, cfg.max_bytes
        self.partial = cfg.dest / ".partial"
        self.http, self.ledger, self.executor = http, ledger, executor
        self._hashes: set[str] = set()
        self._notice_tasks: dict[Path, asyncio.Future] = {}

    async def fetch(self, c: Candidate) -> bool:
        """True when stored; False when it duplicated an existing file."""
        tmp, sha, size = await self._fetch_to_partial(c)
        try:
            if sha in self._hashes or self.ledger.has_hash(sha):
                self.ledger.record_decision(c, "duplicate", f"sha256 {sha[:12]} already stored")
                return False
            self._hashes.add(sha)
            try:
                notice = await self._notice_file(c) if c.license_id in NOTICE_LICENSES else None
            except Exception:
                self._hashes.discard(sha)
                raise
            final = self._final_path(c, sha, tmp.suffix)
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, final)
            self.ledger.record_asset(c, sha, size, final.relative_to(self.dest), notice)
            self.ledger.record_decision(c, "accepted")
            return True
        finally:
            self._discard(tmp)

    async def _fetch_to_partial(self, c: Candidate) -> tuple[Path, str, int]:
        if c.via_ytdlp:
            await self.http.limiter.wait(urlparse(c.download_url).hostname or "")
            return await asyncio.get_running_loop().run_in_executor(
                self.executor, ytdlp_fetch, c.download_url, self.partial / uuid.uuid4().hex, self.max_bytes)
        tmp = self.partial / f"{uuid.uuid4().hex}{c.ext}"
        try:
            sha, size = await self.http.download(c.download_url, tmp, self.max_bytes)
        except BaseException:
            self._discard(tmp)
            raise
        return tmp, sha, size

    def _discard(self, tmp: Path) -> None:
        tmp.unlink(missing_ok=True)
        if tmp.parent != self.partial:
            shutil.rmtree(tmp.parent, ignore_errors=True)

    def _final_path(self, c: Candidate, sha: str, ext: str) -> Path:
        slug = slugify(c.title) or "untitled"
        letter = slug[0].upper() if slug[0].isalpha() else "0-9"
        return self.dest / CATEGORIES[c.category].folder / letter / f"{slug}--{c.source}-{sha[:10]}{ext.lower()}"

    async def _notice_file(self, c: Candidate) -> str:
        """Fetch a collection's LICENSE/NOTICE once and share it across its files."""
        path = self.dest / "_licenses" / f"{c.source}--{slugify(c.collection, 120) or 'misc'}.txt"
        if path not in self._notice_tasks:
            self._notice_tasks[path] = asyncio.ensure_future(self._write_notices(path, c.notice_urls))
        await self._notice_tasks[path]
        return str(path.relative_to(self.dest))

    async def _write_notices(self, path: Path, urls: tuple) -> None:
        parts = [f"==== {url} ====\n{await self.http.get_text(url)}" for url in urls]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n\n".join(parts), encoding="utf-8")


# ── Orchestrator ─────────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(self, cfg: Config, agents: list[SourceAgent], inspector: MetadataInspector,
                 downloader: DownloadAgent, ledger: Ledger):
        self.cfg, self.agents, self.inspector, self.downloader, self.ledger = cfg, agents, inspector, downloader, ledger
        self.candidates: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self.downloads: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self.reserved: Counter = Counter()   # accepted + in flight, per category
        self.done: Counter = Counter()
        self.stats: Counter = Counter()
        self.inflight: set[tuple[str, str]] = set()
        self.saturated = asyncio.Event()     # every requested category (or --max-total) is filled

    def _full(self, category: str) -> bool:
        return (self.reserved[category] >= self.cfg.limit_per_category
                or sum(self.reserved.values()) >= self.cfg.max_total)

    async def run(self) -> None:
        producers = [
            asyncio.ensure_future(self._produce(agent, key))
            for agent in self.agents for key in self.cfg.categories
            if agent.media & CATEGORIES[key].media
        ]
        workers = ([asyncio.ensure_future(self._inspect_loop()) for _ in range(self.cfg.inspect_workers)]
                   + [asyncio.ensure_future(self._download_loop()) for _ in range(self.cfg.download_workers)])
        try:
            # Stop searching as soon as quotas are met instead of waiting out rate-limit sleeps.
            searching = asyncio.ensure_future(asyncio.gather(*producers, return_exceptions=True))
            filled = asyncio.ensure_future(self.saturated.wait())
            await asyncio.wait({searching, filled}, return_when=asyncio.FIRST_COMPLETED)
            for task in (filled, searching, *producers):
                task.cancel()
            await self.candidates.join()
            await self.downloads.join()
        finally:
            for task in producers + workers:
                task.cancel()
            await asyncio.gather(*producers, *workers, return_exceptions=True)

    async def _produce(self, agent: SourceAgent, category: str) -> None:
        cat = CATEGORIES[category]
        for media in sorted(agent.media & cat.media):
            for query in cat.queries:
                if self._full(category):
                    return
                try:
                    async for candidate in agent.search(query, media, category, self.cfg.per_query):
                        if self._full(category):
                            return
                        self.stats["candidates"] += 1
                        await self.candidates.put(candidate)
                except Exception as exc:
                    self.stats["search_errors"] += 1
                    log.warning("%s: %s query %r failed: %s", agent.name, media, query, exc)

    async def _inspect_loop(self) -> None:
        while True:
            candidate = await self.candidates.get()
            try:
                await self._inspect(candidate)
            except Exception as exc:
                self.stats["inspect_errors"] += 1
                log.warning("inspect %s/%s failed: %s", candidate.source, candidate.source_id, exc)
            finally:
                self.candidates.task_done()

    async def _inspect(self, c: Candidate) -> None:
        key = (c.source, c.source_id)
        if key in self.inflight or self.ledger.seen(*key):
            self.stats["already_have"] += 1
            return
        self.inflight.add(key)
        handed_off = False
        try:
            if self._full(c.category):
                return
            reason = await self.inspector.inspect(c)
            if reason:
                self.stats["rejected"] += 1
                log.debug("reject %s/%s: %s", c.source, c.source_id, reason)
                self.ledger.record_decision(c, "rejected", reason)
                return
            if self._full(c.category):
                return
            self.reserved[c.category] += 1
            await self.downloads.put(c)
            handed_off = True
        finally:
            if not handed_off:
                self.inflight.discard(key)

    async def _download_loop(self) -> None:
        while True:
            c = await self.downloads.get()
            stored = False
            try:
                if self.cfg.dry_run:
                    log.info("[dry-run] %-13s %-10s %-14s %s", CATEGORIES[c.category].folder, c.source, c.license_id, c.title)
                    stored = True
                else:
                    stored = await self.downloader.fetch(c)
                    self.stats["stored" if stored else "duplicates"] += 1
                    if stored:
                        log.info("✓ %-13s %-10s %-14s %s", CATEGORIES[c.category].folder, c.source, c.license_id, c.title)
            except Exception as exc:
                self.stats["download_errors"] += 1
                log.warning("download %s/%s failed: %s", c.source, c.source_id, exc)
                self.ledger.record_decision(c, "failed", str(exc)[:500])
            finally:
                if stored:
                    self.done[c.category] += 1
                    if (sum(self.done.values()) >= self.cfg.max_total
                            or all(self.done[k] >= self.cfg.limit_per_category for k in self.cfg.categories)):
                        self.saturated.set()
                else:
                    self.reserved[c.category] -= 1
                self.inflight.discard((c.source, c.source_id))
                self.downloads.task_done()

    def report(self) -> None:
        log.info("── summary %s──", "(dry run) " if self.cfg.dry_run else "")
        for key in self.cfg.categories:
            log.info("  %-16s %3d / %d", CATEGORIES[key].folder, self.done[key], self.cfg.limit_per_category)
        log.info("  %s", ", ".join(f"{k}={v}" for k, v in sorted(self.stats.items())) or "no candidates")


# ── Wiring / CLI ─────────────────────────────────────────────────────────────

def build_agents(cfg: Config, http: Http) -> list[SourceAgent]:
    agents = []
    for name in cfg.sources:
        agent = SOURCES[name](http, cfg)
        if agent.key_env and agent.key_required and not agent.key:
            log.warning("skipping %s: set %s in the environment", name, agent.key_env)
        elif agent.platform_licensed and not cfg.allow_platform_licenses:
            log.info("skipping %s: its license is not CC0/PD/MIT/Apache (see --allow-platform-licenses)", name)
        else:
            agents.append(agent)
    return agents


async def amain(cfg: Config) -> None:
    partial = cfg.dest / ".partial"
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    ledger = Ledger(cfg.db_path)
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=60)
    connector = aiohttp.TCPConnector(limit=cfg.download_workers * 2 + 8)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector,
                                     headers={"User-Agent": cfg.user_agent}) as session:
        http = Http(session, RateLimiter(HOST_RPS, DEFAULT_RPS), cfg.retries)
        renderer = BrowserRenderer(cfg.user_agent) if cfg.use_browser else None
        verifier = PageVerifier(http, renderer, cfg.user_agent) if cfg.verify_pages else None
        with ThreadPoolExecutor(max_workers=cfg.threads, thread_name_prefix="ytdlp") as executor:
            orchestrator = Orchestrator(
                cfg, build_agents(cfg, http), MetadataInspector(cfg, verifier),
                DownloadAgent(cfg, http, ledger, executor), ledger,
            )
            try:
                await orchestrator.run()
            finally:
                if renderer:
                    await renderer.close()
                ledger.export(cfg.dest / "manifest.json")
                shutil.rmtree(partial, ignore_errors=True)
                orchestrator.report()


def _csv_choice(parser: argparse.ArgumentParser, flag: str, value: str, choices) -> tuple:
    if value == "all":
        return tuple(sorted(choices))
    picked = tuple(dict.fromkeys(v.strip() for v in value.split(",") if v.strip()))
    unknown = [v for v in picked if v not in choices]
    if unknown or not picked:
        parser.error(f"{flag}: unknown {unknown or value!r}; choose from {', '.join(sorted(choices))} or 'all'")
    return picked


def parse_args(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(
        description="Harvest CC0 / public-domain / MIT / Apache-2.0 SFX and editing assets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--dest", type=Path, default=Path("asset_library"), help="library root")
    p.add_argument("--db", type=Path, help="SQLite audit ledger (default: <dest>/assets.db)")
    p.add_argument("--sources", default="all", help=f"comma list: {', '.join(SOURCES)}")
    p.add_argument("--categories", default="all", help=f"comma list: {', '.join(CATEGORIES)}")
    p.add_argument("--limit-per-category", type=int, default=25, help="max new assets per category this run")
    p.add_argument("--max-total", type=int, default=200, help="max new assets this run")
    p.add_argument("--per-query", type=int, default=20, help="candidates pulled per query per source")
    p.add_argument("--files-per-item", type=int, default=5, help="max files from one archive.org item / GitHub repo")
    p.add_argument("--inspect-workers", type=int, default=4)
    p.add_argument("--download-workers", type=int, default=6)
    p.add_argument("--threads", type=int, default=2, help="thread pool size for yt-dlp")
    p.add_argument("--max-file-mb", type=float, default=150.0)
    p.add_argument("--retries", type=int, default=4)
    p.add_argument("--verify-pages", action="store_true",
                   help="also confirm the license on the human-facing source page")
    p.add_argument("--use-browser", action="store_true",
                   help="with --verify-pages, render JS-only pages in headless Chromium (Playwright)")
    p.add_argument("--allow-platform-licenses", action="store_true",
                   help="also accept Pexels / Pixabay licenses (commercial use OK, redistribution limited)")
    p.add_argument("--dry-run", action="store_true", help="search and inspect, but download nothing")
    p.add_argument("--contact", default=os.environ.get("HARVESTER_CONTACT", ""),
                   help="email or URL for the User-Agent (Wikimedia asks for one)")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args(argv)
    for flag in ("limit_per_category", "max_total", "per_query", "files_per_item",
                 "inspect_workers", "download_workers", "threads", "retries"):
        if getattr(a, flag) < 1:
            p.error(f"--{flag.replace('_', '-')} must be >= 1")
    if a.use_browser and not a.verify_pages:
        p.error("--use-browser only applies with --verify-pages")
    dest = a.dest.expanduser().resolve()
    return Config(
        dest=dest, db_path=(a.db or dest / "assets.db").expanduser().resolve(),
        sources=_csv_choice(p, "--sources", a.sources, SOURCES),
        categories=_csv_choice(p, "--categories", a.categories, CATEGORIES),
        limit_per_category=a.limit_per_category, max_total=a.max_total, per_query=a.per_query,
        files_per_item=a.files_per_item, inspect_workers=a.inspect_workers,
        download_workers=a.download_workers, threads=a.threads, max_bytes=int(a.max_file_mb * 1024 * 1024),
        retries=a.retries, verify_pages=a.verify_pages, use_browser=a.use_browser,
        allow_platform_licenses=a.allow_platform_licenses, dry_run=a.dry_run, contact=a.contact,
        verbose=a.verbose,
    )


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    cfg.dest.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if cfg.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(), logging.FileHandler(cfg.dest / "harvest.log", encoding="utf-8")],
    )
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    try:
        asyncio.run(amain(cfg))
    except KeyboardInterrupt:
        log.warning("interrupted; ledger and manifest cover every finished download")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
