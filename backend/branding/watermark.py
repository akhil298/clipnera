"""Listening Spark: the watermark whose sparkle and level bars follow the clip's voice.

The pieces (name, tile per loudness level, level bar per height) are drawn by
``branding/motion/source/kit.js`` and saved under ``static/branding``; this
module measures the clip's loudness frame by frame and stacks the matching
pieces into a transparent overlay video.
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

SAMPLE_RATE = 16000
# Loudness below this share of the clip's loud parts reads as silence.
NOISE_FLOOR = 0.12
# Level-meter smoothing per frame: rise fast, fall slower.
ATTACK, RELEASE = 0.6, 0.18


def loudness(video: Path, fps: float, frames: int, has_audio: bool) -> np.ndarray:
    """Per-frame loudness in 0..1, smoothed like a level meter; all zero without audio."""
    if not has_audio or frames <= 0:
        return np.zeros(max(frames, 0))
    decoded = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(video),
         "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
        capture_output=True,
    )
    if decoded.returncode != 0:
        raise RuntimeError(f"Reading the clip's audio failed: {decoded.stderr.decode('utf-8', 'ignore')[-300:]}")
    power = np.square(np.frombuffer(decoded.stdout, dtype=np.float32), dtype=np.float64)
    edges = np.minimum((np.arange(frames + 1) * SAMPLE_RATE / fps).astype(np.int64), len(power))
    summed = np.concatenate(([0.0], np.cumsum(power)))
    rms = np.sqrt((summed[edges[1:]] - summed[edges[:-1]]) / np.maximum(edges[1:] - edges[:-1], 1))
    peak = float(np.percentile(rms, 95)) if rms.any() else 0.0
    if peak <= 0:
        return np.zeros(frames)
    level = np.clip(rms / peak, 0.0, 1.0) ** 0.8
    level[level < NOISE_FLOOR] = 0.0
    smoothed, current = np.empty(frames), 0.0
    for i, value in enumerate(level):
        current += (value - current) * (ATTACK if value > current else RELEASE)
        smoothed[i] = current
    return smoothed


@dataclass(frozen=True)
class Sprite:
    image: Image.Image
    x: int
    y: int


class SparkOverlay:
    """The watermark's pieces scaled for one frame size."""

    def __init__(self, layout_path: Path, short_side: int) -> None:
        layout = json.loads(layout_path.read_text())
        scale = short_side / layout["ref"]

        def load(entry: dict) -> Sprite:
            image = Image.open(layout_path.parent / entry["file"]).convert("RGBA")
            size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
            return Sprite(image.resize(size, Image.Resampling.LANCZOS), round(entry["x"] * scale), round(entry["y"] * scale))

        self.size = (math.ceil(layout["box"]["w"] * scale), math.ceil(layout["box"]["h"] * scale))
        self.right = round(layout["anchor"]["right"] * scale)
        self.top = round(layout["anchor"]["top"] * scale)
        self.bar_lag_s = layout["bar_lag_s"]
        self.tiles = [load(entry) for entry in layout["tiles"]]
        self.bars = [load(entry) for entry in layout["bars"]]
        self.bar_x = [round(x * scale) for x in layout["bar_x"]]
        word = load(layout["word"])
        self._base = Image.new("RGBA", self.size)
        self._base.alpha_composite(word.image, (word.x, word.y))

    def position(self, frame_width: int) -> tuple[int, int]:
        """Top-left corner of the overlay on a frame of this width: the top-right corner."""
        return frame_width - self.right, self.top

    def frame(self, level: int, bar_levels: list[int]) -> bytes:
        """RGBA bytes of one frame: the tile at ``level``, each bar at its own level."""
        image = self._base.copy()
        for x, bar_level in zip(self.bar_x, bar_levels):
            bar = self.bars[bar_level]
            image.alpha_composite(bar.image, (x, bar.y))
        tile = self.tiles[level]
        image.alpha_composite(tile.image, (tile.x, tile.y))
        return image.tobytes()

    def write(self, levels: np.ndarray, fps: float, out: Path) -> None:
        """Encode one overlay frame per loudness value to a transparent video at ``out``."""
        steps = np.rint(levels * (len(self.tiles) - 1)).astype(int)
        lag = round(self.bar_lag_s * fps)
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{self.size[0]}x{self.size[1]}", "-framerate", f"{fps:.6f}",
            "-i", "-", "-c:v", "qtrle", str(out),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i, level in enumerate(steps):
                bars = [int(steps[max(0, i - k * lag)]) for k in range(len(self.bar_x))]
                proc.stdin.write(self.frame(int(level), bars))
        finally:
            proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", "ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"Watermark overlay failed: {stderr[-300:]}")
