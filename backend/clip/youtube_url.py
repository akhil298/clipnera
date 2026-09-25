"""YouTube link validation — YouTube is the only video source Clipnera ingests.

Mirrored on the frontend by `extractYoutubeVideoId` in `frontend/lib/utils/urlParser.ts`.
"""
import re
from urllib.parse import parse_qs, urlparse

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
_ID_PATH_PREFIXES = {"embed", "shorts", "live", "v"}
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def extract_youtube_video_id(url: str) -> str | None:
    """Return the video id of a YouTube video link, or None for any other URL."""
    url = url.strip()
    if not re.match(r"https?://", url, re.IGNORECASE):
        url = f"https://{url}"
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    first = parts[0] if parts else ""
    if host == "youtu.be":
        candidate = first
    elif host in _YOUTUBE_HOSTS and first == "watch":
        candidate = parse_qs(parsed.query).get("v", [""])[0]
    elif host in _YOUTUBE_HOSTS and first in _ID_PATH_PREFIXES and len(parts) > 1:
        candidate = parts[1]
    else:
        return None
    return candidate if _VIDEO_ID.fullmatch(candidate) else None


def canonical_youtube_url(url: str) -> str:
    """Normalize a YouTube video link to its canonical watch URL; raise ValueError for anything else."""
    video_id = extract_youtube_video_id(url)
    if not video_id:
        raise ValueError("Only YouTube video links are supported")
    return f"https://www.youtube.com/watch?v={video_id}"
