"""Small FFmpeg helpers the agents share: run a command, grab frames, pack contact sheets, measure levels."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from core.logging_config import get_logger

log = get_logger(__name__)

# Output frame and timing of every reel.
W, H, FPS = 1080, 1920, 30
# Steps between the source and the final file re-encode at near-lossless quality; speed matters more than size there.
INTERMEDIATE_PRESET = "superfast"
# The vision endpoint takes at most 50 images a request; frames are packed into sheets to fit.
MAX_IMAGES = 48
FONT = "/System/Library/Fonts/Helvetica.ttc" if Path("/System/Library/Fonts/Helvetica.ttc").exists() else \
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


class MediaError(RuntimeError):
    pass


def run(cmd: list[str]) -> str:
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        raise MediaError(f"{cmd[0]} failed: {done.stderr.strip()[-600:]}")
    return done.stdout


def probe(path: str | Path) -> dict:
    """Duration, size, fps and whether there is audio, rotation applied to the size."""
    data = json.loads(run(["ffprobe", "-v", "error", "-show_entries",
                           "format=duration:stream=codec_type,width,height,r_frame_rate:stream_side_data=rotation:stream_tags=rotate",
                           "-of", "json", str(path)]))
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    width, height, fps, rotation = 0, 0, 30.0, 0
    if video:
        width, height = int(video.get("width") or 0), int(video.get("height") or 0)
        num, _, den = str(video.get("r_frame_rate", "30/1")).partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 30.0
        rotation = abs(int(float((video.get("tags") or {}).get("rotate", 0) or
                                 next((d.get("rotation", 0) for d in video.get("side_data_list", []) if "rotation" in d), 0))))
        if rotation in (90, 270):
            width, height = height, width
    return {"duration": float(data.get("format", {}).get("duration") or 0.0), "width": width, "height": height,
            "fps": fps if 1 < fps < 121 else 30.0, "has_audio": audio, "has_video": video is not None}


def frame(path: str | Path, t: float, width: int = 540) -> np.ndarray | None:
    """One BGR frame at ``t`` scaled to ``width`` (height keeps the aspect, even)."""
    info = probe(path)
    if not info["width"]:
        return None
    height = int(round(width * info["height"] / info["width"] / 2) * 2)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(path), "-frames:v", "1",
                          "-vf", f"scale={width}:{height}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(height, width, 3) if len(raw) == width * height * 3 else None


def jpeg(image: np.ndarray, quality: int = 80) -> bytes:
    import cv2

    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return data.tobytes() if ok else b""


def stamp(image: np.ndarray, text: str) -> np.ndarray:
    import cv2

    out = image.copy()
    cv2.rectangle(out, (0, 0), (8 + 11 * len(text), 24), (0, 0, 0), -1)
    cv2.putText(out, text, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 255), 1, cv2.LINE_AA)
    return out


def sheets(items: list[tuple[str, np.ndarray]], columns: int, rows: int, cell: int = 320) -> list[bytes]:
    """Labelled frames packed into ``columns`` x ``rows`` sheets, read left to right, top to bottom."""
    import cv2

    if not items:
        return []
    per = columns * rows
    out = []
    for start in range(0, len(items), per):
        chunk = items[start:start + per]
        tiles = []
        for label, image in chunk:
            h = int(round(cell * image.shape[0] / image.shape[1]))
            tiles.append(stamp(cv2.resize(image, (cell, h), interpolation=cv2.INTER_AREA), label))
        th = max(t.shape[0] for t in tiles)
        canvas = np.zeros((th * rows, cell * columns, 3), np.uint8)
        for k, tile in enumerate(tiles):
            r, c = divmod(k, columns)
            canvas[r * th:r * th + tile.shape[0], c * cell:(c + 1) * cell] = tile
        used_rows = (len(chunk) + columns - 1) // columns
        out.append(jpeg(canvas[: used_rows * th]))
    return out


def strip(path: str | Path, t0: float, t1: float, cell: int = 240) -> bytes:
    """Three frames of a stretch (start, middle, end) side by side, for checking a label against its shot."""
    frames = [frame(path, t, cell) for t in (t0 + 0.12, (t0 + t1) / 2, max(t0 + 0.2, t1 - 0.12))]
    frames = [f for f in frames if f is not None]
    if not frames:
        return b""
    h = min(f.shape[0] for f in frames)
    return jpeg(np.hstack([f[:h] for f in frames]))


def mean_rgb(path: str | Path, times: list[float]) -> np.ndarray:
    values = [f.reshape(-1, 3)[:, ::-1].mean(axis=0) for f in (frame(path, t, 96) for t in times) if f is not None]
    return np.mean(values, axis=0) if values else np.array([128.0, 128.0, 128.0])


def rms_db(samples: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(samples))) + 1e-9)) if samples.size else -90.0


def read_wav(path: str | Path) -> tuple[np.ndarray, int]:
    from scipy.io import wavfile

    rate, raw = wavfile.read(str(path))
    data = raw.astype(np.float32)
    if np.issubdtype(raw.dtype, np.integer):
        data /= float(np.iinfo(raw.dtype).max)
    return (data.mean(axis=1) if data.ndim > 1 else data), rate


def loudness(path: str | Path) -> float:
    """Integrated loudness (LUFS) of a file's audio."""
    done = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                          capture_output=True, text=True)
    lines = [l for l in done.stderr.splitlines() if l.strip().startswith("I:")]
    try:
        return float(lines[-1].split()[1]) if lines else -70.0
    except (IndexError, ValueError):
        return -70.0
