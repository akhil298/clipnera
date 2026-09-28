"""Colour: per-shot exposure correction plus one named look for the whole reel.

Looks are built from FFmpeg's own colour filters rather than LUT files, so
there is nothing to license and nothing to download, and they run on CPU at
render speed.
"""

from __future__ import annotations

LOOKS: dict[str, str] = {
    "natural": "eq=contrast=1.03:saturation=1.05",
    "clean_bright": "eq=brightness=0.03:contrast=1.05:saturation=1.08,unsharp=5:5:0.35",
    "warm_film": "colorbalance=rs=0.05:gs=0.01:bs=-0.06:rh=0.04:bh=-0.05,eq=contrast=1.06:saturation=0.95",
    "teal_orange": "colorbalance=rs=-0.06:bs=0.08:rh=0.08:gh=0.01:bh=-0.07,eq=contrast=1.08:saturation=1.1",
    "moody": "eq=contrast=1.12:brightness=-0.03:saturation=0.8,vignette=PI/5",
    "vivid": "eq=contrast=1.08:saturation=1.3",
    "bw_punch": "hue=s=0,eq=contrast=1.25",
}
LOOK_LABELS: dict[str, str] = {
    "natural": "Natural", "clean_bright": "Clean & bright", "warm_film": "Warm film", "teal_orange": "Teal & orange",
    "moody": "Moody", "vivid": "Vivid", "bw_punch": "Black & white",
}
DEFAULT_LOOK = "natural"
# Mean grey level the exposure correction pulls each shot toward.
TARGET_BRIGHTNESS = 118.0
MAX_EXPOSURE_SHIFT = 0.1


def exposure_filter(brightness: float | None) -> str | None:
    """An ``eq`` brightness shift toward a normal exposure; None when the shot is already fine."""
    if brightness is None:
        return None
    shift = max(-MAX_EXPOSURE_SHIFT, min(MAX_EXPOSURE_SHIFT, (TARGET_BRIGHTNESS - brightness) / 255 * 0.6))
    return f"eq=brightness={shift:.3f}" if abs(shift) >= 0.01 else None


def look_filter(name: str) -> str:
    return LOOKS.get(name, LOOKS[DEFAULT_LOOK])
