"""Watching the footage on CPU: file facts, shots, quality, faces and proxies.

Nothing here decodes every frame. Shots and quality come from keyframes only
(``-skip_frame nokey``), sampled once a second at 256 px wide, which is about
five times cheaper than a full decode and fits a free-tier CPU. Every function
takes local paths and returns plain data, so it can run in a worker process
or a Lambda without the database.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from broll.renditions import run
from video_processor.editing import SHOT_CUT_CORRELATION
from video_processor.face_detection import FaceDetector

SAMPLE_WIDTH = 256
# A shot shorter than this is merged into the one before it: flashes and
# camera bumps are not shots.
MIN_SHOT_SECONDS = 1.0
# Laplacian variance of a 256 px frame below which it reads as blurred.
BLUR_THRESHOLD = 40.0
DARK_THRESHOLD = 35.0
BRIGHT_THRESHOLD = 225.0
PROXY_SHORT_SIDE = 480


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    has_audio: bool
    has_video: bool


@dataclass
class Shot:
    start: float
    end: float
    blur: float
    brightness: float
    motion: float
    face_x: float | None = None
    faces: int = 0
    frame: np.ndarray | None = field(default=None, repr=False)

    @property
    def usable(self) -> bool:
        return self.blur >= BLUR_THRESHOLD and DARK_THRESHOLD <= self.brightness <= BRIGHT_THRESHOLD

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3), "end": round(self.end, 3), "blur": round(self.blur, 1),
            "brightness": round(self.brightness, 1), "motion": round(self.motion, 2),
            "face_x": None if self.face_x is None else round(self.face_x, 3), "faces": self.faces, "usable": self.usable,
        }


async def probe_media(path: str) -> MediaInfo:
    """Duration, display size (rotation applied) and which streams the file has."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    data = json.loads(stdout or b"{}")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    width, height = int((video or {}).get("width") or 0), int((video or {}).get("height") or 0)
    if abs(_rotation(video or {})) in (90, 270):
        width, height = height, width
    return MediaInfo(
        duration=float((data.get("format") or {}).get("duration") or 0.0),
        width=width, height=height, has_audio=audio is not None, has_video=video is not None,
    )


def _rotation(stream: dict[str, Any]) -> int:
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            return int(float(side["rotation"]))
    return int(float((stream.get("tags") or {}).get("rotate") or 0))


async def extract_audio(src: str, out: str) -> None:
    """16 kHz mono WAV, the input speech recognition wants."""
    await run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", src,
               "-vn", "-ac", "1", "-ar", "16000", out])


def sample_size(width: int, height: int) -> tuple[int, int]:
    """Frame size for analysis: 256 px wide, even height, source aspect."""
    if width <= 0 or height <= 0:
        return SAMPLE_WIDTH, SAMPLE_WIDTH
    return SAMPLE_WIDTH, max(2, round(SAMPLE_WIDTH * height / width / 2) * 2)


async def sample_frames(src: str, info: MediaInfo) -> list[tuple[float, np.ndarray]]:
    """One BGR frame a second, decoded from keyframes only."""
    width, height = sample_size(info.width, info.height)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-skip_frame", "nokey", "-i", src,
        "-vf", f"fps=1,scale={width}:{height}", "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Could not read frames: {stderr.decode('utf-8', 'ignore')[-200:]}")
    size = width * height * 3
    count = len(stdout) // size
    return [(float(i), np.frombuffer(stdout, np.uint8, size, i * size).reshape(height, width, 3)) for i in range(count)]


def frame_stats(frame: np.ndarray) -> tuple[float, float, np.ndarray, np.ndarray]:
    """(blur, brightness, colour histogram, grey image) of one frame."""
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return float(cv2.Laplacian(grey, cv2.CV_64F).var()), float(grey.mean()), hist, grey


def detect_shots(frames: list[tuple[float, np.ndarray]], duration: float) -> list[Shot]:
    """Shots from colour-histogram changes between sampled frames, with per-shot quality."""
    if not frames:
        return [Shot(0.0, duration, blur=0.0, brightness=0.0, motion=0.0)] if duration > 0 else []
    stats = [frame_stats(frame) for _, frame in frames]
    starts = [0]
    for i in range(1, len(frames)):
        if cv2.compareHist(stats[i - 1][2], stats[i][2], cv2.HISTCMP_CORREL) < SHOT_CUT_CORRELATION:
            starts.append(i)
    bounds = [frames[i][0] for i in starts] + [max(duration, frames[-1][0] + 1.0)]
    shots: list[Shot] = []
    for index, first in enumerate(starts):
        last = (starts[index + 1] if index + 1 < len(starts) else len(frames))
        span = range(first, last)
        motion = [float(np.abs(stats[i][3].astype(np.int16) - stats[i - 1][3].astype(np.int16)).mean())
                  for i in span if i > first]
        sharpest = max(span, key=lambda i: stats[i][0])
        shot = Shot(
            start=bounds[index], end=bounds[index + 1],
            blur=float(np.median([stats[i][0] for i in span])),
            brightness=float(np.mean([stats[i][1] for i in span])),
            motion=float(np.mean(motion)) if motion else 0.0,
            frame=frames[sharpest][1],
        )
        if shots and shot.end - shot.start < MIN_SHOT_SECONDS:
            shots[-1].end = shot.end
        else:
            shots.append(shot)
    if len(shots) > 1 and shots[0].end - shots[0].start < MIN_SHOT_SECONDS:
        first_shot = shots.pop(0)
        shots[0].start = first_shot.start
    return shots


def add_faces(shots: list[Shot], detector: FaceDetector | None = None) -> None:
    """Horizontal centre of the largest face in each shot's sharpest frame, for the 9:16 crop."""
    detector = detector or FaceDetector()
    for shot in shots:
        if shot.frame is None:
            continue
        faces = detector.detect(shot.frame)
        shot.faces = len(faces)
        if faces:
            biggest = max(faces, key=lambda f: f.box.width * f.box.height)
            shot.face_x = biggest.box.center[0]


def proxy_cmd(src: str, out: str, info: MediaInfo) -> list[str]:
    """A small H.264 copy with audio the browser preview can play (HEVC and MOV often cannot)."""
    scale = f"scale=-2:{PROXY_SHORT_SIDE}" if info.width >= info.height else f"scale={PROXY_SHORT_SIDE}:-2"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", src,
           "-vf", f"{scale},fps=24", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "64k", "-ac", "1"] if info.has_audio else ["-an"]
    return cmd + ["-movflags", "+faststart", out]
