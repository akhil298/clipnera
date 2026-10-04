"""Reels kept as references: a motion graphic seen elsewhere, saved to study.

A reference is somebody else's work. It lives under ``references/`` beside the
catalogue, one folder per reel holding ``reel.mp4`` and ``reference.json``, and
never enters ``catalog.json``, so no search offers it to an edit.
"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from core.config import get_settings
from core.logging_config import get_logger
from motion_library.catalog import library_root

log = get_logger(__name__)

REFERENCES_DIR = "references"
# Reels move here once studied (see motion_library.editing_assets).
ANALYZED_DIR = "analyzed"
VIDEO_NAME = "reel.mp4"
NOTES_NAME = "reference.json"
MEASURE_DIR = "measure"
MEASUREMENTS_NAME = "measurements.json"
_LINK = re.compile(r"https?://(?:www\.)?instagram\.com/[^\s]+", re.IGNORECASE)
_REEL = re.compile(r"instagram\.com/(?:[^/?#]+/)?(?:reels?|p|tv)/([\w-]+)", re.IGNORECASE)
# Share-sheet links carry no reel id; Instagram redirects them to the reel.
_SHARE = re.compile(r"instagram\.com/share/", re.IGNORECASE)
RESOLVE_TIMEOUT_SECONDS = 15.0


class ReelError(Exception):
    """The reel could not be saved; the message is fit to show the person who sent it."""


@dataclass(frozen=True)
class Reference:
    id: str
    folder: Path
    # False when the reel was already in the library.
    new: bool


def reel_link(text: str) -> str | None:
    """The first Instagram link in ``text``."""
    found = _LINK.search(text or "")
    return found.group(0) if found else None


def reel_id(url: str) -> str | None:
    found = _REEL.search(url)
    return found.group(1) if found else None


async def save_reel(link: str) -> Reference:
    """Download the reel behind ``link`` into the library, once."""
    url = await _resolved(link)
    id_ = reel_id(url)
    if id_ is None:
        raise ReelError("That link is not an Instagram reel or post.")
    root = library_root() / REFERENCES_DIR
    folder = root / id_
    for kept in (folder, library_root() / ANALYZED_DIR / id_):
        if (kept / VIDEO_NAME).is_file():
            return Reference(id_, kept, new=False)
    root.mkdir(parents=True, exist_ok=True)
    # Downloaded beside its final place and moved in whole, so a folder is never half a reel.
    with tempfile.TemporaryDirectory(dir=root, prefix=".incoming-") as incoming:
        info = await asyncio.to_thread(_download, url, Path(incoming))
        (Path(incoming) / NOTES_NAME).write_text(json.dumps(_notes(url, info), indent=2), encoding="utf-8")
        Path(incoming).rename(folder)
        # The context manager removes its folder on exit; it has moved, so give it one to remove.
        Path(incoming).mkdir()
    log.info("Motion reference saved: %s", id_)
    return Reference(id_, folder, new=True)


async def _resolved(link: str) -> str:
    if not _SHARE.search(link):
        return link
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=RESOLVE_TIMEOUT_SECONDS) as client:
            return str((await client.get(link)).url)
    except httpx.HTTPError as exc:
        raise ReelError("Could not open that share link.") from exc


def _download(url: str, folder: Path) -> dict[str, Any]:
    import yt_dlp

    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "allowed_extractors": ["instagram"],
        "outtmpl": str(folder / "reel.%(ext)s"),
        "merge_output_format": "mp4",
        "socket_timeout": 15,
        "retries": 1,
    }
    cookies = get_settings().INSTAGRAM_COOKIES_PATH.strip()
    if cookies:
        options["cookiefile"] = str(Path(cookies).expanduser())
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        log.warning("Reel download failed: %s", exc)
        raise ReelError("Instagram would not let me download that reel. It may be private, or need a login.") from exc
    if not (folder / VIDEO_NAME).is_file():
        raise ReelError("That post has no single video to save.")
    return info or {}


def _notes(url: str, info: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_url": url,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "creator": info.get("channel") or info.get("uploader") or "",
        "caption": info.get("description") or "",
        "duration_s": info.get("duration"),
        "width": info.get("width"),
        "height": info.get("height"),
    }
