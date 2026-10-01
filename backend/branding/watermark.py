"""Listening Spark: the watermark whose sparkle and level bars follow the clip's voice.

It arrives the way short-form viewers expect a maker's mark to: after the
opening headline, a vertical "MADE WITH" badge rises on the left edge, rolls up
into the top-left corner the headline left, and the name wipes in.

The pieces (name, tile per loudness level, level bar per height) are drawn by
``branding/motion/source/kit.js`` and saved under ``static/branding``; this
module measures the clip's loudness frame by frame and stacks the matching
pieces into a transparent overlay video.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SAMPLE_RATE = 16000
# Loudness below this share of the clip's loud parts reads as silence.
NOISE_FLOOR = 0.12
# Level-meter smoothing per frame: rise fast, fall slower.
ATTACK, RELEASE = 0.6, 0.18
# The mark's size on screen relative to its authored layout.
WATERMARK_SCALE = 0.9
# Where the mark settles and how it gets there, in pixels of a 1080-wide
# vertical frame (scaled with the frame's short side): the icon's left edge and
# the mark's centre top-left, where the headline card sat; the badge's resting
# height beside the speaker, and how far below that it slides in from.
ICON_LEFT, MARK_CENTRE_Y = 124, 298
BADGE_REST_Y, BADGE_RISE = 640, 300
# Seconds from the clip's start: the headline card holds the opening alone, then
# the badge slides in, holds beside the speaker, rolls up into the corner, and
# the name wipes in beside the icon before the level bars come up.
BADGE_IN, BADGE_REST, ROLL, LAND, NAME_DONE, BARS_IN = 4.3, 4.8, 6.9, 7.4, 8.1, 0.3
BADGE_LABEL = "MADE WITH"
BADGE_FONT = Path(__file__).resolve().parent.parent / "static" / "fonts" / "Montserrat-Bold.ttf"
# The badge's type, letter spacing and the gap above the icon, in layout pixels.
BADGE_TYPE_PX, BADGE_TRACKING_PX, BADGE_GAP_PX = 45, 8, 22
# A soft dark halo under the mark keeps it legible on bright or warm footage.
HALO_BLUR_PX, HALO_OPACITY = 10, 0.45


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


def _ease_out(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) ** 3


def _ease_in_out(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _faded(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 1.0:
        return image
    faded = image.copy()
    faded.putalpha(image.getchannel("A").point(lambda a: round(a * opacity)))
    return faded


def _halo(image: Image.Image, blur: float) -> Image.Image:
    halo = Image.new("RGBA", image.size, (0, 0, 0, 0))
    halo.putalpha(image.getchannel("A").filter(ImageFilter.GaussianBlur(blur)).point(lambda a: round(a * HALO_OPACITY)))
    return halo


class SparkOverlay:
    """The Listening Spark mark for one frame size, animated into the top-left corner.

    The overlay covers the frame's left column from its top corner, which
    ``position`` reports as (0, 0): the mark moves inside it. The tile's icon
    (its opaque core, without the glow) lines up with the badge and then with
    the name, so it reads as one object travelling into place.
    """

    def __init__(self, layout_path: Path, short_side: int) -> None:
        layout = json.loads(layout_path.read_text())
        unit = short_side / layout["ref"]
        scale = unit * WATERMARK_SCALE

        def load(entry: dict) -> tuple[Image.Image, int, int]:
            image = Image.open(layout_path.parent / entry["file"]).convert("RGBA")
            size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
            return image.resize(size, Image.Resampling.LANCZOS), round(entry["x"] * scale), round(entry["y"] * scale)

        self.tiles = [load(entry)[0] for entry in layout["tiles"]]
        self.bars = [load(entry) for entry in layout["bars"]]
        self.bar_x = [round(x * scale) for x in layout["bar_x"]]
        self.bar_lag_s = layout["bar_lag_s"]
        self.word, self.word_x, self.word_y = load(layout["word"])
        tile = self.tiles[-1]
        icon_left, self.icon_top = tile.getchannel("A").point(lambda a: 255 if a > 200 else 0).getbbox()[:2]
        self.mark_x = round(ICON_LEFT * unit) - icon_left
        self.icon_centre_x = self.mark_x + tile.width / 2
        self.settled_y = round(MARK_CENTRE_Y * unit - tile.height / 2)
        self.rest_y = round(BADGE_REST_Y * unit - tile.height / 2)
        self.start_y = self.rest_y + round(BADGE_RISE * unit)
        self.label = self._label(scale)
        self.label_gap = round(BADGE_GAP_PX * scale)
        self.halo_blur = HALO_BLUR_PX * scale
        right = max(self.word_x + self.word.width, max(self.bar_x) + self.bars[0][0].width)
        self.size = (self.mark_x + right + round(self.halo_blur * 2), self.start_y + tile.height)
        # The settled mark's halo barely changes with the bars, so it is drawn once.
        settled = Image.new("RGBA", self.size)
        self._place_mark(settled, len(self.tiles) - 1, [len(self.bars) - 1] * len(self.bar_x), self.settled_y, 1.0, 1.0)
        self._settled_halo = _halo(settled, self.halo_blur)

    @staticmethod
    def _label(scale: float) -> Image.Image:
        """BADGE_LABEL set in caps and turned to read top to bottom."""
        font = ImageFont.truetype(str(BADGE_FONT), max(1, round(BADGE_TYPE_PX * scale)))
        tracking = BADGE_TRACKING_PX * scale
        width = sum(font.getlength(c) for c in BADGE_LABEL) + tracking * (len(BADGE_LABEL) - 1)
        ascent, descent = font.getmetrics()
        text = Image.new("RGBA", (math.ceil(width), ascent + descent), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text)
        x = 0.0
        for char in BADGE_LABEL:
            draw.text((x, 0), char, font=font, fill=(255, 255, 255, 255))
            x += font.getlength(char) + tracking
        return text.rotate(-90, expand=True)

    def position(self, frame_width: int) -> tuple[int, int]:
        """Top-left corner of the overlay on the frame: the frame's own corner."""
        return 0, 0

    def _place_mark(
        self, image: Image.Image, level: int, bar_levels: list[int], top: int, name_share: float, bars_opacity: float,
    ) -> None:
        image.alpha_composite(self.tiles[level], (self.mark_x, top))
        cut = round(self.word.width * name_share)
        if cut > 0:
            image.alpha_composite(self.word.crop((0, 0, cut, self.word.height)), (self.mark_x + self.word_x, top + self.word_y))
        if bars_opacity > 0:
            for x, bar_level in zip(self.bar_x, bar_levels):
                bar, _, bar_y = self.bars[bar_level]
                image.alpha_composite(_faded(bar, bars_opacity), (self.mark_x + x, top + bar_y))

    def frame(self, t: float, level: int, bar_levels: list[int]) -> bytes:
        """RGBA bytes of the overlay ``t`` seconds into the clip."""
        image = Image.new("RGBA", self.size)
        if t < BADGE_IN:
            return image.tobytes()
        if t >= NAME_DONE + BARS_IN:
            image.alpha_composite(self._settled_halo)
            self._place_mark(image, level, bar_levels, self.settled_y, 1.0, 1.0)
            return image.tobytes()

        if t < BADGE_REST:
            top = self.start_y + (self.rest_y - self.start_y) * _ease_out((t - BADGE_IN) / (BADGE_REST - BADGE_IN))
        elif t < ROLL:
            top = self.rest_y
        else:
            top = self.rest_y + (self.settled_y - self.rest_y) * _ease_in_out((t - ROLL) / (LAND - ROLL))
        top = round(top)
        arriving = min(1.0, (t - BADGE_IN) / (BADGE_REST - BADGE_IN))
        mark = Image.new("RGBA", self.size)
        label_alpha = arriving * (1.0 - min(1.0, max(0.0, (t - ROLL) / (LAND - ROLL))))
        if label_alpha > 0:
            # The label rides above the icon and runs off the top as it rolls up.
            bottom = top + self.icon_top - self.label_gap
            label = _faded(self.label, label_alpha)
            if bottom - label.height < 0:
                label = label.crop((0, label.height - bottom, label.width, label.height)) if bottom > 0 else None
            if label is not None:
                mark.alpha_composite(label, (round(self.icon_centre_x - label.width / 2), max(0, bottom - label.height)))
        name_share = _ease_out((t - LAND) / (NAME_DONE - LAND)) if t >= LAND else 0.0
        bars_opacity = min(1.0, (t - NAME_DONE) / BARS_IN) if t >= NAME_DONE else 0.0
        self._place_mark(mark, level, bar_levels, top, name_share, bars_opacity)
        if arriving < 1.0:
            mark = _faded(mark, arriving)
        image.alpha_composite(_halo(mark, self.halo_blur))
        image.alpha_composite(mark)
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
                proc.stdin.write(self.frame(i / fps, int(level), bars))
        finally:
            proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", "ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"Watermark overlay failed: {stderr[-300:]}")
