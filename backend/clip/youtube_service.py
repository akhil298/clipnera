from __future__ import annotations

import asyncio
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import time
from clients.services.s3 import S3
from core.config import get_settings
from core.logging_config import get_logger

settings = get_settings()
log = get_logger(__name__)


@dataclass(frozen=True)
class QualityOption:
    """Represents a video quality option."""
    format_id: str
    label: str  # e.g. "1080p", "720p", "audio only"
    height: Optional[int]
    fps: Optional[float]
    vcodec: Optional[str]
    acodec: Optional[str]
    filesize_approx: Optional[int]
    is_default: bool = False


@dataclass(frozen=True)
class PrefetchResult:
    """Metadata and quality options for a video."""
    title: str
    duration: Optional[float]
    uploader: Optional[str]
    thumbnail: Optional[str]
    qualities: list[QualityOption]


@dataclass(frozen=True)
class DownloadResult:
    """Result of a download operation."""
    local_path: str
    content_type: str
    size_bytes: int
    metadata: dict = field(default_factory=dict)


class YouTubeService:
    """Fetch and download YouTube videos."""

    VIDEO_ID_PATTERNS = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})",
    ]

    _progress_store: Dict[str, Dict[str, Any]] = {}
    _progress_lock = asyncio.Lock()

    def __init__(self) -> None:
        self._s3 = S3()
        self._bucket = settings.S3_BUCKET_NAME
        self._progress_hooks: Dict[str, callable] = {}

    @classmethod
    async def get_progress(cls, key: str) -> Dict[str, Any]:
        async with cls._progress_lock:
            return dict(cls._progress_store.get(key, {}))

    @classmethod
    async def set_progress(cls, key: str, data: Dict[str, Any]) -> None:
        async with cls._progress_lock:
            cls._progress_store[key] = data

    @classmethod
    async def clear_progress(cls, key: str) -> None:
        async with cls._progress_lock:
            cls._progress_store.pop(key, None)

    @classmethod
    def set_progress_sync(cls, key: str, data: Dict[str, Any]) -> None:
        """Sync progress writer safe to call from executor threads."""
        cls._progress_store[key] = data

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    )

    def _yt_dlp_base_options(self) -> dict:
        """Base yt-dlp options shared across all extraction/download calls.

        Includes a browser-like User-Agent to reduce bot-detection and
        cookie support via two methods:
        1. YOUTUBE_COOKIES_BROWSER: yt-dlp reads cookies directly from browser (recommended).
           Set to browser name, e.g. "chrome", "firefox", "edge".
        2. YOUTUBE_COOKIES_PATH: path to a manually exported cookies.txt file.

        If neither is set, the project falls back to its bundled backend/youtube_cookies.txt file.
        """
        options: dict = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 15,
            "retries": 1,
            "fragment_retries": 1,
            "http_headers": {
                "User-Agent": self.USER_AGENT,
            },
        }

        deno_path = shutil.which("deno")
        if deno_path:
            options["js_runtimes"] = {"deno": deno_path}
            options["remote_components"] = ["ejs:github"]
            log.info(f"yt-dlp JavaScript runtime enabled: {deno_path}")

        cookie_browser = os.environ.get("YOUTUBE_COOKIES_BROWSER")
        if cookie_browser:
            options["cookiesfrombrowser"] = (cookie_browser,)
            log.info(f"YouTube cookies will be read from browser: {cookie_browser}")
            return options

        cookie_path = os.environ.get("YOUTUBE_COOKIES_PATH")
        backend_dir = Path(__file__).resolve().parent.parent
        if cookie_path and Path(cookie_path).name.startswith(".env"):
            log.warning("Ignoring invalid YOUTUBE_COOKIES_PATH pointing to an environment file")
            cookie_path = None

        if cookie_path:
            configured_path = Path(cookie_path).expanduser()
            if not configured_path.is_absolute():
                backend_relative_path = backend_dir / configured_path
                if backend_relative_path.exists():
                    cookie_path = str(backend_relative_path)

        if not cookie_path:
            candidate_paths = [
                backend_dir / "youtube_cookies.txt",
                Path.cwd() / "youtube_cookies.txt",
                backend_dir / ".." / "youtube_cookies.txt",
            ]
            for candidate in candidate_paths:
                if candidate.exists():
                    cookie_path = str(candidate.resolve())
                    break

        if cookie_path:
            cookie_file = Path(cookie_path).expanduser()
            if cookie_file.exists():
                options["cookiefile"] = str(cookie_file.resolve())
                log.info(f"YouTube cookies file loaded from {cookie_file.resolve()}")
            else:
                log.warning(f"YOUTUBE_COOKIES_PATH points to a missing file: {cookie_path}")

        return options

    def _content_type_from_path(self, path: str) -> str:
        """Determine content type from file extension."""
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        return {
            "mp4": "video/mp4",
            "mkv": "video/x-matroska",
            "webm": "video/webm",
            "mov": "video/quicktime",
            "m4a": "audio/mp4",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
        }.get(ext, "application/octet-stream")

    def _build_quality_options(self, formats: list[dict]) -> list[QualityOption]:
        """Collapse yt-dlp format list into a deduplicated quality menu."""
        seen_heights: set = set()
        options: list[QualityOption] = []

        # video+audio combined or best-video streams, sorted highest res first
        video_formats = [
            f for f in formats if f.get("vcodec") not in (None, "none") and f.get("height")
        ]
        video_formats.sort(
            key=lambda f: (f.get("height") or 0, f.get("fps") or 0), reverse=True
        )

        for f in video_formats:
            h = f.get("height")
            if h in seen_heights:
                continue
            seen_heights.add(h)
            fps = f.get("fps")
            label = f"{h}p" + (f" {int(fps)}fps" if fps and fps > 30 else "")
            options.append(
                QualityOption(
                    format_id=f"bestvideo[height<={h}]+bestaudio/best[height<={h}]",
                    label=label,
                    height=h,
                    fps=fps,
                    vcodec=f.get("vcodec"),
                    acodec=f.get("acodec"),
                    filesize_approx=f.get("filesize_approx") or f.get("filesize"),
                )
            )

        # always offer audio-only
        options.append(
            QualityOption(
                format_id="bestaudio/best",
                label="Audio only",
                height=None,
                fps=None,
                vcodec=None,
                acodec=None,
                filesize_approx=None,
            )
        )

        # mark the best video quality (or audio-only if no video) as default
        if options:
            default_idx = 0
            options = [
                QualityOption(**{**o.__dict__, "is_default": i == default_idx})
                for i, o in enumerate(options)
            ]

        return options

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        for pattern in YouTubeService.VIDEO_ID_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def fetch_metadata(self, url: str) -> PrefetchResult | None:
        """Extract metadata and quality options from a URL without downloading. Raises ValueError on failure."""
        try:
            import yt_dlp
        except ImportError:
            log.error("yt-dlp Python package not installed. Install with: pip install yt-dlp")
            return None

        def _extract():
            options = self._yt_dlp_base_options()
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _extract)
        except Exception as e:
            log.error(f"Failed to fetch metadata: {type(e).__name__}: {e}")
            return None

        if not info:
            return None

        qualities = self._build_quality_options(info.get("formats") or [])
        return PrefetchResult(
            title=info.get("title") or "",
            duration=info.get("duration"),
            uploader=info.get("uploader"),
            thumbnail=info.get("thumbnail"),
            qualities=qualities,
        )

    async def get_available_formats(self, url: str) -> dict:
        """Return available video and audio formats for a URL."""
        try:
            import yt_dlp
        except ImportError:
            log.error("yt-dlp Python package not installed. Install with: pip install yt-dlp")
            return {"title": "", "duration": 0, "thumbnail": "", "channel": "", "video": [], "audio": []}

        def _extract():
            options = self._yt_dlp_base_options()
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _extract)
        except Exception as e:
            log.error(f"Failed to fetch formats: {type(e).__name__}: {e}")
            return {"title": "", "duration": 0, "thumbnail": "", "channel": "", "video": [], "audio": []}

        if not info:
            return {"title": "", "duration": 0, "thumbnail": "", "channel": "", "video": [], "audio": []}

        video_formats: list[dict] = []
        audio_formats: list[dict] = []

        for f in info.get("formats") or []:
            height = f.get("height")
            vcodec = f.get("vcodec") or ""
            acodec = f.get("acodec") or ""
            filesize = f.get("filesize") or f.get("filesize_approx") or 0

            fmt = {
                "format_id": f.get("format_id") or "",
                "ext": f.get("ext") or "",
                "resolution": f"{height}p" if height else ("audio only" if not vcodec or vcodec == "none" else "unknown"),
                "width": f.get("width") or 0,
                "height": height or 0,
                "filesize": filesize,
                "vcodec": vcodec,
                "acodec": acodec,
                "abr": int(f.get("abr") or 0),
                "type": "video" if vcodec and vcodec != "none" else "audio",
            }

            if height and vcodec and vcodec != "none":
                video_formats.append(fmt)
            elif acodec and acodec != "none":
                audio_formats.append(fmt)

        video_formats.sort(key=lambda f: f["height"] or 0, reverse=True)
        audio_formats.sort(key=lambda f: f["abr"] or 0, reverse=True)

        return {
            "title": info.get("title") or "",
            "duration": int(info.get("duration") or 0),
            "thumbnail": info.get("thumbnail") or "",
            "channel": info.get("uploader") or "Unknown",
            "video": video_formats,
            "audio": audio_formats,
        }

    async def download_and_store(self, url: str, user_id: str, project_id: str, format_id: str | None = None) -> Dict[str, Any]:
        """Download YouTube video to local folder and store in S3."""
        try:
            import yt_dlp
        except ImportError:
            log.error("yt-dlp Python package not installed. Install with: pip install yt-dlp")
            raise ValueError("yt-dlp not installed")

        video_id = self.extract_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        # Fetch metadata for the video
        prefetch = await self.fetch_metadata(url)
        if not prefetch:
            raise ValueError("Failed to fetch video metadata")

        download_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "download_videos",
        )
        os.makedirs(download_dir, exist_ok=True)
        output_template = os.path.join(download_dir, "%(id)s.%(ext)s")

        log.info(f"[{project_id}] Starting download of video: {video_id}")
        await self.set_progress(project_id, {"status": "downloading", "percent": 0.0, "total": None, "speed": None, "eta": None})

        def make_progress_hook(pid: str):
            last_update_time = [None]  # Track time for speed calculation
            
            def hook(d: dict):
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    percent = (downloaded / total * 100) if total else 0.0
                    
                    # Get speed from yt-dlp or calculate it
                    speed = d.get('speed', None)
                    speed_string = d.get('speed_string', None)
                    eta_seconds = d.get('eta', None)

                    # Prefer speed_string for display; fall back to bytes/s formatting
                    if speed_string:
                        speed = speed_string
                    elif speed and downloaded > 0:
                        speed = self._format_bytes(int(speed)) + "/s"

                    # Format ETA from yt-dlp (seconds remaining)
                    eta = None
                    if isinstance(eta_seconds, (int, float)) and eta_seconds >= 0:
                        eta = self._format_duration(int(eta_seconds))

                    # Fallback: calculate ETA manually if yt-dlp didn't provide one
                    if eta is None and speed and downloaded > 0 and total > 0:
                        remaining_bytes = total - downloaded
                        try:
                            # Parse speed string to get bytes per second (e.g. "4.9MiB/s" or "4.9 MB/s")
                            cleaned = speed.replace("/s", "").strip()
                            parts = cleaned.split()
                            if len(parts) >= 2:
                                speed_value = float(parts[0])
                                unit = parts[1][0].upper()
                            else:
                                # No unit, treat as bytes/s
                                speed_value = float(parts[0])
                                unit = "B"
                            multiplier = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3}.get(unit, 1)
                            speed_bps = speed_value * multiplier
                            if speed_bps > 0:
                                remaining_seconds = int(remaining_bytes / speed_bps)
                                eta = self._format_duration(remaining_seconds)
                        except Exception:
                            eta = None
                    
                    # Log progress to terminal
                    log.info(f"[{pid}] Download: {percent:.1f}% | {self._format_bytes(downloaded)}/{self._format_bytes(total) if total else '?'} | Speed: {speed or '?'} | ETA: {eta or '?'}")
                    
                    asyncio.run_coroutine_threadsafe(
                        self.set_progress(pid, {
                            "status": "downloading",
                            "percent": round(percent, 1),
                            "total": self._format_bytes(total) if total else None,
                            "speed": speed,
                            "eta": eta,
                        }),
                        loop,
                    )
                elif d['status'] == 'finished':
                    log.info(f"[{pid}] ✓ Download completed, video merging finished")
            return hook

        loop = asyncio.get_event_loop()
        ydl_opts = {
            **self._yt_dlp_base_options(),
            'format': format_id or 'bv*+ba/b',
            'merge_output_format': 'mp4',
            'outtmpl': output_template,
            'noprogress': True,
            'progress_hooks': [make_progress_hook(project_id)],
        }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        try:
            info = await loop.run_in_executor(None, _download)
        except Exception as e:
            error_msg = str(e)
            log.error(f"[{project_id}] ✗ Download failed: {error_msg}")
            await self.set_progress(project_id, {"status": "error", "message": error_msg})
            if "not available" in error_msg.lower():
                raise ValueError("Video not available. It may be private, restricted, or an active live stream.")
            raise ValueError(f"Download failed: {error_msg}")

        # Find downloaded file
        downloaded_file = os.path.join(download_dir, f"{video_id}.mp4")
        if not os.path.exists(downloaded_file):
            for f in os.listdir(download_dir):
                if f.startswith(video_id) and f.endswith((".mp4", ".webm", ".mkv")):
                    downloaded_file = os.path.join(download_dir, f)
                    break

        if not os.path.exists(downloaded_file):
            await self.set_progress(project_id, {"status": "error", "message": "Downloaded file not found"})
            raise FileNotFoundError("Downloaded file not found")

        file_size = os.path.getsize(downloaded_file)
        title = prefetch.title or os.path.splitext(os.path.basename(downloaded_file))[0]
        duration = prefetch.duration or 0

        log.info(f"[{project_id}] ✓ Video file ready: {os.path.basename(downloaded_file)} ({self._format_bytes(file_size)})")
        log.info(f"[{project_id}] Starting S3 upload to {self._bucket}...")
        log.info(f"[{project_id}] File: {os.path.basename(downloaded_file)} | Size: {self._format_bytes(file_size)}")
        await self.set_progress(project_id, {"status": "uploading", "percent": 5.0, "total": self._format_bytes(file_size), "speed": None, "eta": "Uploading to cloud..."})

        s3_key = f"videos/{user_id}/{project_id}/{video_id}.mp4"

        def _format_eta(seconds: float) -> str:
            if seconds is None or seconds <= 0 or seconds == float("inf"):
                return "Calculating..."
            seconds = int(seconds)
            if seconds < 60:
                return f"{seconds}s"
            m, s = divmod(seconds, 60)
            if m < 60:
                return f"{m}m {s}s"
            h, m = divmod(m, 60)
            return f"{h}h {m}m"

        def _upload_to_s3():
            """Upload file to S3 using fast parallel multipart upload (10 workers, 50MB chunks)."""
            import time as _time

            log.info(f"[{project_id}] Using existing S3 bucket: {self._bucket}")
            log.info(f"[{project_id}] [UPLOAD_START] Starting fast upload: {self._format_bytes(file_size)}")

            uploaded_bytes = 0
            start_time = _time.monotonic()
            last_log_time = start_time
            last_log_bytes = 0

            def _callback(bytes_amount: int) -> None:
                nonlocal uploaded_bytes, last_log_time, last_log_bytes
                uploaded_bytes += bytes_amount
                now = _time.monotonic()
                elapsed = now - start_time
                overall_speed = uploaded_bytes / elapsed if elapsed > 0 else 0
                remaining = max(0, file_size - uploaded_bytes)
                eta_seconds = (remaining / overall_speed) if overall_speed > 0 else None

                if (now - last_log_time) >= 0.5 or uploaded_bytes >= file_size:
                    window_bytes = uploaded_bytes - last_log_bytes
                    window_time = now - last_log_time if now > last_log_time else 0.001
                    window_speed = window_bytes / window_time if window_time > 0 else 0
                    last_log_time = now
                    last_log_bytes = uploaded_bytes

                    upload_percent = (uploaded_bytes / file_size) * 100 if file_size else 0
                    overall_percent = 5.0 + (upload_percent / 100.0) * 70.0

                    log.info(
                        f"[{project_id}] Uploaded {self._format_bytes(uploaded_bytes)}/{self._format_bytes(file_size)} "
                        f"({(uploaded_bytes / file_size * 100):.1f}%) | {self._format_bytes(int(window_speed))}/s"
                    )

                    self.set_progress_sync(project_id, {
                        "status": "uploading",
                        "percent": round(overall_percent, 1),
                        "upload_percent": round(upload_percent, 1),
                        "total": self._format_bytes(file_size),
                        "uploaded": self._format_bytes(uploaded_bytes),
                        "speed": self._format_bytes(int(window_speed)) + "/s" if window_speed else None,
                        "avg_speed": self._format_bytes(int(overall_speed)) + "/s" if overall_speed else None,
                        "eta": _format_eta(eta_seconds) if eta_seconds is not None else "Calculating...",
                        "elapsed": _format_eta(int(elapsed)),
                        "phase": "uploading",
                        "message": f"Uploading {self._format_bytes(uploaded_bytes)} of {self._format_bytes(file_size)}",
                    })

            self._s3.upload_file(
                bucket=self._bucket,
                key=s3_key,
                file_path=downloaded_file,
                content_type="video/mp4",
                callback=_callback,
            )

            log.info(f"[{project_id}] [UPLOAD_DONE] ✓ File successfully uploaded to S3 ({self._format_bytes(file_size)})")
            return True

        # Run upload in executor to avoid blocking
        log.info(f"[{project_id}] Queuing S3 upload task (parallel, 50MB chunks)...")
        try:
            await loop.run_in_executor(None, _upload_to_s3)
        except Exception as e:
            log.error(f"[{project_id}] ✗ S3 upload failed: {str(e)}")
            await self.set_progress(project_id, {"status": "error", "message": f"S3 upload failed: {str(e)}"})
            raise ValueError(f"S3 upload failed: {str(e)}")

        log.info(f"[{project_id}] ✓ S3 upload completed ({self._format_bytes(file_size)}) -> s3://{self._bucket}/{s3_key}")
        await self.set_progress(project_id, {"status": "uploading", "percent": 75.0, "total": self._format_bytes(file_size), "speed": None, "eta": "Generating link..."})

        log.info(f"[{project_id}] Generating presigned URL (expires in 1 hour)...")
        try:
            presigned_url = self._s3.generate_presigned_url(
                bucket=self._bucket,
                key=s3_key,
                expires_in=3600,
            )
            log.info(f"[{project_id}] ✓ Presigned URL generated")
        except Exception as e:
            log.error(f"[{project_id}] Failed to generate presigned URL: {str(e)}")
            presigned_url = ""

        await self.set_progress(project_id, {"status": "done", "percent": 100.0})
        log.info(f"[{project_id}] ✓✓✓ COMPLETE - Video ready for processing! File: s3://{self._bucket}/{s3_key}")

        return {
            "title": title,
            "duration_seconds": int(duration or 0),
            "duration_formatted": self._format_duration(duration or 0),
            "file_size": file_size,
            "s3_key": s3_key,
            "s3_bucket": self._bucket,
            "presigned_url": presigned_url,
            "resolution": f"{info.get('width', '?')}x{info.get('height', '?')}",
            "aspect_ratio": info.get("aspect_ratio", "16:9"),
            "thumbnail_url": prefetch.thumbnail or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            "channel_title": prefetch.uploader or "Unknown",
            "original_url": url,
            "local_path": downloaded_file,
        }


    @staticmethod
    def _format_duration(seconds: int | float) -> str:
        seconds = int(seconds or 0)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    @staticmethod
    def _format_bytes(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
