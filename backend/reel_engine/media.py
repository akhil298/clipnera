"""Small FFmpeg helpers the agents share: run a command, grab frames, pack contact sheets, measure levels."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from core.logging_config import get_logger

log = get_logger(__name__)

# Where burned-in subtitles usually reach (share of the height from that edge) when they cannot be measured.
TEXT_BAND = {"top": 0.12, "bottom": 0.24}

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
    # A still image has no timeline: seeking it, even to 0, returns no frame.
    seek = ["-ss", f"{t:.3f}"] if t > 0 else []
    raw = subprocess.run(["ffmpeg", "-v", "error", *seek, "-i", str(path), "-frames:v", "1",
                          "-vf", f"scale={width}:{height}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(height, width, 3) if len(raw) == width * height * 3 else None


def text_band(path: str | Path, side: str, samples: int = 16) -> float:
    """How far (share of the height, from the ``side`` edge) the footage's burned-in subtitles reach. Lettering is
    rows dense with sharp vertical strokes, which a scene's edges are not; a band is not found, a usual one is assumed."""
    import cv2

    duration = probe(path)["duration"] or 0.0
    rows = []
    for k in range(samples):
        image = frame(path, duration * (k + 0.5) / samples, 640)
        if image is not None:
            grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
            rows.append((np.abs(cv2.Sobel(grey, cv2.CV_32F, 1, 0)) > 120).mean(axis=1))
    if not rows:
        return TEXT_BAND[side]
    reach = lettered_reach(np.mean(rows, axis=0), side)
    return reach if reach is not None else TEXT_BAND[side]


def lettered_reach(profile: np.ndarray, side: str) -> float | None:
    """How far lettering reaches from ``side`` in a row profile of sharp vertical strokes, or None when there is none."""
    profile = profile if side == "top" else profile[::-1]
    reach = int(len(profile) * 0.35)
    lettered = np.nonzero(profile[:reach] > max(0.04, 3 * float(np.median(profile))))[0]
    return min(0.35, (lettered[-1] + 1) / len(profile) + 0.02) if lettered.size else None


def edge_band(profile: np.ndarray, side: str) -> float | None:
    """How far a band of lettering reaches from ``side``, when it is one: it starts near the edge (within the outer
    tenth at the top; a lower third sits a little higher, so the outer 15% at the bottom) and runs on with no long gap.
    A poster on the wall or hair high in the frame is not a ticker."""
    rows = profile if side == "top" else profile[::-1]
    n = len(rows)
    median = float(np.median(profile))
    hits = np.nonzero(rows[:int(n * 0.35)] > max(0.04, 3 * median))[0]
    if not hits.size or hits[0] > n * (0.10 if side == "top" else 0.15):
        return None
    # Once a band starts, lighter lettering (a banner's second, thinner line) still belongs to it.
    lighter = np.nonzero(rows[:int(n * 0.35)] > max(0.04, 2 * median))[0]
    end, gap = hits[0], max(2, int(n * 0.03))
    for k in lighter[lighter > hits[0]]:
        if k - end > gap:
            break
        end = k
    return min(0.35, (end + 1) / n + 0.02)


def burned_bands(path: str | Path, samples: int = 16, least: int = 2) -> dict[str, float]:
    """Text bands along the top or bottom edge anywhere in the footage - a news ticker, a lower third, an end-card
    footer that shows up late - as {side: reach}. Each frame is read on its own, so text seen in only part of the video
    still counts once it shows in ``least`` frames."""
    import cv2

    duration = probe(path)["duration"] or 0.0
    seen: dict[str, list[float]] = {"top": [], "bottom": []}
    # A name banner (lower third) is usually up only in the first seconds: those are read closely too.
    times = sorted({t for t in (0.5, 1.5, 2.5, 3.5) if t < duration} | {duration * (k + 0.5) / samples for k in range(samples)})
    for t in times:
        image = frame(path, t, 640)
        if image is None:
            continue
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        profile = (np.abs(cv2.Sobel(grey, cv2.CV_32F, 1, 0)) > 120).mean(axis=1)
        for side in seen:
            reach = edge_band(profile, side)
            if reach is not None:
                seen[side].append(reach)
    return {side: max(r) for side, r in seen.items() if len(r) >= least}


COVER_AT = 1.2  # seconds into a reel: the hook headline is up and the speaker is on screen


def cover(path: str | Path, width: int = 540) -> bytes:
    """A JPEG cover of a finished reel (its frame at COVER_AT, or its first frame when shorter), or b"" if unreadable."""
    try:
        seconds = probe(path)["duration"] or 0.0
        image = frame(path, min(COVER_AT, max(0.0, seconds - 0.1)), width)
    except MediaError:  # a cover is never worth failing a delivered reel over
        return b""
    return jpeg(image, 85) if image is not None else b""


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
