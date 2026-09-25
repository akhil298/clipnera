"""The exact file a post publishes, fetched from S3 and probed.

The source is the clip's latest captioned render when there is one (what the
user previews and downloads), else its primary render. The bucket stays
private: files are streamed down to a temp directory for upload, and platforms
that pull (Instagram) get a presigned URL to that one object, valid for minutes.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from clients.services.s3 import S3
from clip_generation.model import GeneratedClip
from core.config import get_settings
from social.providers.base import ClipFile, ErrorKind, PlatformError

PROBE_TIMEOUT_SECONDS = 60


def source_of(clip: GeneratedClip) -> tuple[str, str]:
    """(bucket, key) of the file to publish, or PlatformError when the clip has no stored render."""
    bucket = clip.s3_bucket or get_settings().S3_BUCKET_NAME
    burned = clip.burned_subtitle_path
    # Older rows hold a local path in burned_subtitle_path; only S3 keys are usable.
    if burned and not Path(burned).is_absolute():
        return bucket, burned
    if clip.s3_key:
        return bucket, clip.s3_key
    raise PlatformError(ErrorKind.PERMANENT, "clip_not_rendered", "This clip has no finished video to publish yet.")


def probe(path: Path) -> dict:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PlatformError(ErrorKind.TRANSIENT, "probe_failed", "Could not inspect the clip file.") from exc
    if result.returncode != 0:
        raise PlatformError(ErrorKind.PERMANENT, "probe_failed", "The clip file could not be read.")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PlatformError(ErrorKind.PERMANENT, "probe_failed", "The clip file could not be read.") from exc


def _fps(rate: str | None) -> float:
    num, _, den = (rate or "0/1").partition("/")
    try:
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def clip_file_from_probe(path: Path, info: dict, presign=None) -> ClipFile:
    streams = info.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise PlatformError(ErrorKind.PERMANENT, "no_video_stream", "The clip file has no video.")
    fmt = info.get("format") or {}
    return ClipFile(
        path=path,
        size_bytes=path.stat().st_size,
        duration_seconds=float(fmt.get("duration") or video.get("duration") or 0.0),
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=_fps(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        video_codec=str(video.get("codec_name") or ""),
        audio_codec=audio.get("codec_name") if audio else None,
        audio_sample_rate=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        container=str(fmt.get("format_name") or ""),
        presign=presign,
    )


@asynccontextmanager
async def downloaded_clip(clip: GeneratedClip, s3: S3 | None = None) -> AsyncIterator[ClipFile]:
    """Download the clip's publishable render to a temp dir and probe it; removed on exit."""
    bucket, key = source_of(clip)
    s3 = s3 or S3()
    workdir = Path(tempfile.mkdtemp(prefix="clipnera-publish-"))
    path = workdir / "clip.mp4"
    try:
        try:
            await asyncio.to_thread(s3.download_file, bucket, key, str(path))
        except Exception as exc:
            raise PlatformError(ErrorKind.TRANSIENT, "clip_download_failed", "Could not load the clip file.") from exc
        info = await asyncio.to_thread(probe, path)
        yield clip_file_from_probe(
            path, info, presign=lambda ttl: s3.generate_presigned_url(bucket, key, expires_in=ttl)
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
