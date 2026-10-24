"""Instagram reel and post links for the reel maker, opened and fetched with yt-dlp like YouTube links."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

# instagram.com/reel/<id>, /reels/<id>, /p/<id>, /tv/<id>, also with the account name in front.
INSTAGRAM_LINK = re.compile(r"^https?://(?:www\.|m\.)?instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/([\w-]+)", re.I)


def is_instagram_link(url: str) -> bool:
    return INSTAGRAM_LINK.match(url.strip()) is not None


@dataclass(frozen=True)
class InstagramVideo:
    title: str
    duration: float | None  # Instagram often leaves it out; the file is measured after the download


class InstagramService:
    def _options(self) -> dict:
        options = {"quiet": True, "no_warnings": True, "socket_timeout": 20, "noplaylist": True}
        cookies = Path(get_settings().INSTAGRAM_COOKIES_PATH).expanduser()
        if cookies.is_file():
            options["cookiefile"] = str(cookies)
        return options

    @staticmethod
    def _title(info: dict) -> str:
        who = info.get("uploader") or info.get("channel") or ""
        caption = (info.get("description") or "").strip().splitlines()
        return (caption[0][:120] if caption and caption[0] else "") or (f"Instagram reel by {who}" if who else "Instagram reel")

    async def fetch_metadata(self, url: str) -> InstagramVideo | None:
        """The reel's title and length, or None when it cannot be opened (private, removed, or a login wall)."""
        import yt_dlp

        def _fetch() -> InstagramVideo | None:
            try:
                with yt_dlp.YoutubeDL(self._options()) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as exc:
                log.warning("Instagram link could not be opened: %s", exc)
                return None
            if not info or (info.get("_type") == "playlist" and not info.get("entries")):
                return None
            return InstagramVideo(title=self._title(info), duration=info.get("duration"))

        return await asyncio.to_thread(_fetch)

    async def download_for_edit(self, url: str, folder: Path, max_seconds: int) -> tuple[Path, str]:
        """The reel (at most ``max_seconds``) as MP4 in ``folder``, and its title."""
        import yt_dlp

        def _download() -> tuple[Path, str]:
            options = {
                **self._options(),
                "format": "bv*[height<=1920]+ba/b",
                "merge_output_format": "mp4",
                "outtmpl": str(folder / "source.%(ext)s"),
                "noprogress": True,
                # "<=?" lets a reel through when Instagram gives no length; the caller measures the file.
                "match_filter": yt_dlp.utils.match_filter_func(f"duration <=? {max_seconds}"),
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
            if not path.exists():
                raise ValueError(f"the video is longer than {max_seconds // 60} minutes")
            return path, self._title(info or {})

        return await asyncio.to_thread(_download)


def link_name(url: str) -> str:
    """What a source link points at, for messages: "Instagram reel" or "YouTube video"."""
    return "Instagram reel" if is_instagram_link(url or "") else "YouTube video"
