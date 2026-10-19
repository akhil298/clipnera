"""Cutting a frame of the output's shape out of a source: held, or moving through keyframes."""

from __future__ import annotations

from typing import Any

from edit_engine.keyframes import curve, moves


def crop_filter(zoom: float, crop_x: float | None, size: tuple[int, int] = (9, 16)) -> str:
    """Cut a frame of the output's shape (``size``, 9:16 for a reel) out of any source shape, centred
    on the face (or the middle)."""
    centre = 0.5 if crop_x is None else min(1.0, max(0.0, crop_x))
    width, height = size
    w = f"min(iw\\,ih*{width}/{height})/{zoom:.3f}"
    h = f"min(ih\\,iw*{height}/{width})/{zoom:.3f}"
    return f"crop=w='{w}':h='{h}':x='max(0\\,min(iw-ow\\,{centre:.3f}*iw-ow/2))':y='(ih-oh)*0.45'"


def framing_filters(item: dict[str, Any], size: tuple[int, int]) -> list[str]:
    """Crop and scale a source to the output's shape: held, or moving through its keyframes.

    A moving framing is cropped at its widest (with the pan following ``t``), drawn at twice the
    output size so the zoom moves smoothly, then zoomed in from there frame by frame."""
    motion = item.get("motion") or {}
    zooms, xs = motion.get("zoom"), motion.get("x")
    if not (moves(zooms) or moves(xs)):
        return [crop_filter(item.get("zoom") or 1.0, item.get("crop_x"), size), f"scale={size[0]}:{size[1]}"]
    width, height = size
    zooms = [(t, max(1.0, v), e) for t, v, e in zooms] if zooms else [(0.0, max(1.0, item.get("zoom") or 1.0), "linear")]
    widest = min(v for _, v, _ in zooms)
    centre = f"min(1,max(0,{curve(xs, 't')}))" if xs else f"{min(1.0, max(0.0, item.get('crop_x') or 0.5)):.3f}"
    return [
        f"crop=w='min(iw,ih*{width}/{height})/{widest:.3f}':h='min(ih,iw*{height}/{width})/{widest:.3f}'"
        f":x='max(0,min(iw-ow,{centre}*iw-ow/2))':y='(ih-oh)*0.45'",
        f"scale={width * 2}:{height * 2}",
        f"zoompan=z='({curve(zooms, 'on/30')})/{widest:.4f}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*0.45'"
        f":d=1:s={width}x{height}:fps=30",
        # zoompan's own timestamps confuse a later fps filter; count frames afresh.
        "setpts=N/30/TB",
    ]


def timing_filters(speed: float) -> list[str]:
    """Play a source at ``speed``, at 30 fps: slow motion blends neighbouring frames rather than
    showing each one twice."""
    return [f"setpts=(PTS-STARTPTS)/{speed:.4f}", "framerate=fps=30" if speed < 1 else "fps=30"]
