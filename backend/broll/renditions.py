"""The files every library shot is stored as.

Made once at ingest so a user's render only trims and concatenates: a 9:16
1080x1920 master, a 540x960 proxy for the scene board, and a thumbnail. Stock
audio is dropped; reels carry the speaker's voice and our own music.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

VERTICAL = (1080, 1920)
PROXY = (540, 960)


@dataclass(frozen=True)
class Probe:
    width: int
    height: int
    fps: float
    duration: float


def fill_filter(width: int, height: int) -> str:
    """Scale to cover ``width``x``height`` and centre-crop the overflow (no bars)."""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )


def vertical_cmd(src: str, out: str, start: float, duration: float) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", src,
        "-vf", fill_filter(*VERTICAL), "-an",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", out,
    ]


def proxy_cmd(src: str, out: str) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", src,
        "-vf", f"scale={PROXY[0]}:{PROXY[1]},fps=24", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", out,
    ]


def thumb_cmd(src: str, out: str, at: float) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-ss", f"{at:.3f}", "-i", src, "-frames:v", "1", "-vf", "scale=360:640", "-q:v", "4", out,
    ]


async def run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode('utf-8', 'ignore')[-300:]}")


async def probe(path: str) -> Probe:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate:format=duration", "-of", "json", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    data = json.loads(stdout or b"{}")
    stream = (data.get("streams") or [{}])[0]
    num, _, den = str(stream.get("avg_frame_rate") or "0/1").partition("/")
    try:
        fps = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return Probe(
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        fps=fps,
        duration=float((data.get("format") or {}).get("duration") or 0.0),
    )


async def render_shot(src: str, workdir: Path, start: float, duration: float) -> tuple[Path, Path, Path]:
    """(vertical, proxy, thumbnail) for one shot of ``src``."""
    vertical, proxy_path, thumb = workdir / "vertical.mp4", workdir / "proxy.mp4", workdir / "thumb.jpg"
    await run(vertical_cmd(src, str(vertical), start, duration))
    await run(proxy_cmd(str(vertical), str(proxy_path)))
    await run(thumb_cmd(str(vertical), str(thumb), min(duration / 2, 1.5)))
    return vertical, proxy_path, thumb
