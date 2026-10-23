"""Mattes of the speaker for text set behind them, from a portrait-matting ONNX model.

The model (MODNet, Apache-2.0, ``kit/models/modnet.onnx``; fetched by
``scripts/build_motion_kit.py``) runs on CPU at a reduced size and its matte
is scaled back up. Without the model, ``available()`` is False and beats
placed behind the speaker are drawn in front instead.
"""

from __future__ import annotations

import asyncio
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

from beats.kit import kit_dir
from core.logging_config import get_logger

log = get_logger(__name__)

# The short side the model sees; both sides are rounded to a multiple of 32.
REF_SIDE = 512


def model_path() -> Path:
    return kit_dir() / "models" / "modnet.onnx"


def available() -> bool:
    return model_path().is_file()


@lru_cache(maxsize=1)
def _session():
    import onnxruntime as ort  # Imported here: only clips with behind-the-speaker beats need it.

    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    return ort.InferenceSession(str(model_path()), options, providers=["CPUExecutionProvider"])


def _model_size(width: int, height: int) -> tuple[int, int]:
    scale = REF_SIDE / min(width, height)
    return max(32, round(width * scale / 32) * 32), max(32, round(height * scale / 32) * 32)


def _mattes(src: str, start: float, end: float, width: int, height: int, fps: float, out: str) -> None:
    mw, mh = _model_size(width, height)
    reader = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
         "-i", src, "-vf", f"fps={fps},scale={mw}:{mh}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )
    writer = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
         "-s", f"{mw}x{mh}", "-r", str(fps), "-i", "-", "-vf", f"scale={width}:{height}:flags=bicubic",
         "-c:v", "ffv1", "-pix_fmt", "gray", out],
        stdin=subprocess.PIPE,
    )
    session = _session()
    name = session.get_inputs()[0].name
    frame_bytes = mw * mh * 3
    try:
        while True:
            raw = reader.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            image = np.frombuffer(raw, np.uint8).reshape(mh, mw, 3).astype(np.float32) / 255.0
            tensor = ((image - 0.5) / 0.5).transpose(2, 0, 1)[None]
            matte = session.run(None, {name: tensor})[0][0, 0]
            writer.stdin.write((np.clip(matte, 0, 1) * 255).astype(np.uint8).tobytes())
    finally:
        reader.stdout.close()
        writer.stdin.close()
        reader.wait()
        if writer.wait() != 0:
            raise RuntimeError("matte encode failed")


async def matte_video(src: str, start: float, end: float, width: int, height: int, fps: float, out: str) -> bool:
    """Write the speaker's matte for ``start``..``end`` of ``src`` to ``out``; False when it cannot."""
    if not available():
        return False
    try:
        await asyncio.to_thread(_mattes, src, start, end, width, height, fps, out)
        return Path(out).is_file()
    except Exception as exc:
        log.warning("Speaker matte failed, the beat is drawn in front instead: %s", exc)
        return False
