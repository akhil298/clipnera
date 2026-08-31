from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, Optional

import httpx

from clients.services.s3 import S3
from core.logging_config import get_logger

log = get_logger(__name__)


class YouTubeService:
    """Fetch and download YouTube videos."""

    VIDEO_ID_PATTERNS = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})",
    ]

    _progress_store: Dict[str, Dict[str, Any]] = {}
    _progress_lock = asyncio.Lock()

    def __init__(self) -> None:
        self._s3 = S3()
        self._bucket = "clipnera-videos"
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

    async def _yt_dlp_metadata(self, url: str) -> Dict[str, Any] | None:
        """Fetch video metadata using yt-dlp Python API."""
        try:
            import yt_dlp
        except ImportError:
            log.error("yt-dlp Python package not installed. Install with: pip install yt-dlp")
            return None

        def _extract():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, _extract)
            if not data:
                return None
            return {
                "title": data.get("title"),
                "duration": data.get("duration"),
                "width": data.get("width"),
                "height": data.get("height"),
                "aspect_ratio": data.get("aspect_ratio"),
                "thumbnail": data.get("thumbnail"),
                "uploader": data.get("uploader"),
                "channel": data.get("channel"),
            }
        except Exception as e:
            log.error(f"yt-dlp metadata error: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        for pattern in YouTubeService.VIDEO_ID_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def fetch_metadata(self, url: str) -> Dict[str, Any] | None:
        video_id = self.extract_video_id(url)
        if not video_id:
            return None

        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(oembed_url)
                if response.status_code != 200:
                    return None
                data = response.json()

                return {
                    "title": data.get("title", "Untitled"),
                    "thumbnail_url": data.get("thumbnail_url", f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"),
                    "channel_title": data.get("author_name", "Unknown"),
                    "channel_url": data.get("author_url", ""),
                    "duration_seconds": 0,
                    "duration_formatted": "--:--",
                    "resolution": f"{data.get('thumbnail_width', 1280)}x{data.get('thumbnail_height', 720)}",
                    "aspect_ratio": "16:9",
                    "original_url": url,
                }
        except Exception as e:
            log.warning(f"Failed to fetch metadata: {e}")
            return None

    async def download_and_store(self, url: str, user_id: str, project_id: str) -> Dict[str, Any]:
        """Download YouTube video to local folder and store in S3."""
        import yt_dlp

        video_id = self.extract_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        download_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "download_videos",
        )
        os.makedirs(download_dir, exist_ok=True)
        output_template = os.path.join(download_dir, "%(id)s.%(ext)s")

        metadata = await self._yt_dlp_metadata(url)
        if not metadata:
            raise ValueError("Failed to fetch video metadata")

        log.info(f"Downloading video: {video_id}")
        await self.set_progress(project_id, {"status": "downloading", "percent": 0.0, "total": None, "speed": None, "eta": None})

        def make_progress_hook(pid: str):
            def hook(d: dict):
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    percent = (downloaded / total * 100) if total else 0.0
                    speed = d.get('speed_string', None)
                    eta = d.get('eta_string', None)
                    asyncio.run_coroutine_threadsafe(
                        self.set_progress(pid, {
                            "status": "downloading",
                            "percent": round(percent, 1),
                            "total": self._format_bytes(total) if total else None,
                            "speed": f"{self._format_bytes(speed)}/s" if speed else None,
                            "eta": str(eta) if eta else None,
                        }),
                        loop,
                    )
                elif d['status'] == 'finished':
                    asyncio.run_coroutine_threadsafe(
                        self.set_progress(pid, {"status": "uploading", "percent": 100.0}),
                        loop,
                    )
            return hook

        loop = asyncio.get_event_loop()
        ydl_opts = {
            'format': 'bv*+ba/b',
            'noplaylist': True,
            'merge_output_format': 'mp4',
            'outtmpl': output_template,
            'noprogress': True,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [make_progress_hook(project_id)],
        }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        try:
            await loop.run_in_executor(None, _download)
        except Exception as e:
            error_msg = str(e)
            log.error(f"yt-dlp download failed: {error_msg}")
            await self.set_progress(project_id, {"status": "error", "message": error_msg})
            if "not available" in error_msg.lower():
                raise ValueError("Video not available. It may be private, restricted, or an active live stream.")
            raise ValueError(f"Download failed: {error_msg}")

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
        title = metadata.get("title", os.path.splitext(os.path.basename(downloaded_file))[0])
        duration = metadata.get("duration", 0)

        await self.set_progress(project_id, {"status": "uploading", "percent": 100.0, "total": self._format_bytes(file_size), "speed": None, "eta": None})

        s3_key = f"videos/{user_id}/{project_id}/{video_id}.mp4"

        try:
            self._s3.create_bucket(self._bucket)
        except Exception:
            pass

        with open(downloaded_file, "rb") as f:
            self._s3._client.put_object(
                Bucket=self._bucket,
                Key=s3_key,
                Body=f,
                ContentType="video/mp4",
            )

        presigned_url = self._s3.generate_presigned_url(
            bucket=self._bucket,
            key=s3_key,
            expires_in=3600,
        )

        await self.clear_progress(project_id)

        log.info(f"Video stored: video_id={video_id} size={file_size}")

        return {
            "title": title,
            "duration_seconds": duration or 0,
            "duration_formatted": self._format_duration(duration or 0),
            "file_size": file_size,
            "s3_key": s3_key,
            "s3_bucket": self._bucket,
            "presigned_url": presigned_url,
            "resolution": f"{metadata.get('width', '?')}x{metadata.get('height', '?')}",
            "aspect_ratio": metadata.get("aspect_ratio", "16:9"),
            "thumbnail_url": metadata.get("thumbnail", f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"),
            "channel_title": metadata.get("uploader", metadata.get("channel", "Unknown")),
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
