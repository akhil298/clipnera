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


async def grab(asset: Asset, seconds: float, label: str, s3: S3 | None = None) -> bytes | None:
    """A JPEG of ``asset`` at ``seconds`` into it, ``FRAME_HEIGHT`` tall and stamped with ``label``."""
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
    ok, jpeg = cv2.imencode(".jpg", stamp(frame, label), [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return jpeg.tobytes() if ok else None
