"""Still frames for a model to look at: one frame of an asset, labelled with a timecode.

FFmpeg seeks a signed URL directly, so looking at a frame never downloads the whole file.
"""

from __future__ import annotations

import asyncio

import cv2
import numpy as np

from clients.services.s3 import S3
from core.config import get_settings
from editor.timeline import Asset

FRAME_HEIGHT = 360
URL_TTL_SECONDS = 600
JPEG_QUALITY = 80


def timecode(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"


def stamp(tile: np.ndarray, label: str) -> np.ndarray:
    """``label`` burned into the top-left corner, white on black."""
    cv2.rectangle(tile, (0, 0), (12 + 11 * len(label), 26), (0, 0, 0), -1)
    cv2.putText(tile, label, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return tile


# A layer drawn over a still: ("solid", "#RRGGBB", 0) or ("graphic", packed-alpha file, seconds into it).
Layer = tuple[str, str, float]


def _colour(hex_colour: str) -> np.ndarray:
    value = hex_colour.lstrip("#")[:6].ljust(6, "0")
    return np.array([int(value[4:6], 16), int(value[2:4], 16), int(value[0:2], 16)], np.float32)


def _graphic(path: str, seconds: float, size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray] | None:
    """A packed-alpha graphic's colour and matte at ``seconds``, covering ``size`` (w, h) like the export."""
    video = cv2.VideoCapture(path)
    video.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
    ok, frame = video.read()
    video.release()
    if not ok:
        return None
    half = frame.shape[1] // 2
    colour, matte = frame[:, :half], frame[:, half:, 1]
    w, h = size
    k = max(w / colour.shape[1], h / colour.shape[0])
    scaled = (round(colour.shape[1] * k), round(colour.shape[0] * k))
    x, y = (scaled[0] - w) // 2, (scaled[1] - h) // 2
    crop = lambda img: cv2.resize(img, scaled)[y:y + h, x:x + w]  # noqa: E731
    return crop(colour).astype(np.float32), crop(matte).astype(np.float32)[..., None] / 255


def draw_layers(frame: np.ndarray, layers: list[Layer]) -> np.ndarray:
    """The still with the flashes and graphics on it, as the export draws them (edit_engine/compose.py)."""
    out = frame.astype(np.float32)
    for kind, value, seconds in layers:
        if kind == "solid":
            out = np.broadcast_to(_colour(value), out.shape).copy()
        elif (found := _graphic(value, seconds, (frame.shape[1], frame.shape[0]))) is not None:
            colour, alpha = found
            out = out * (1 - alpha) + colour * alpha
    return out.clip(0, 255).astype(np.uint8)


async def grab(asset: Asset, seconds: float, label: str, s3: S3 | None = None, layers: list[Layer] | None = None) -> bytes | None:
    """A JPEG of ``asset`` at ``seconds`` into it, ``FRAME_HEIGHT`` tall, with ``layers`` drawn over it and
    stamped with ``label``."""
    url = (s3 or S3()).generate_presigned_url(get_settings().S3_BUCKET_NAME, asset.proxy or asset.key, URL_TTL_SECONDS)
    at = 0.0 if asset.kind == "image" else max(0.0, seconds)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{at:.3f}", "-i", url,
        "-frames:v", "1", "-vf", f"scale=-2:{FRAME_HEIGHT}", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    frame = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR) if out else None
    if frame is None:
        return None
    if layers:
        frame = await asyncio.to_thread(draw_layers, frame, layers)
    ok, jpeg = cv2.imencode(".jpg", stamp(frame, label), [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return jpeg.tobytes() if ok else None
