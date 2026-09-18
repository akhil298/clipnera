"""Crop geometry shared by every reframing strategy.

Before this module the same helpers were reimplemented in ``reframing``,
``crop_strategy`` and ``content_importance`` with subtly different behaviour,
which is how five of the eight crop strategies ended up treating a box centre as
if it were a top-left origin. Everything that reasons about crops uses these
helpers so that class of bug cannot recur.

All boxes are normalised to 0..1 of the frame and use a top-left origin, which
is the convention FFmpeg's ``crop`` filter expects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)

SUPPORTED_ASPECT_RATIOS: tuple[str, ...] = ("9:16", "1:1", "4:5", "16:9")

DEFAULT_OUTPUT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}


@dataclass(frozen=True)
class Box:
    """A normalised, top-left-origin rectangle."""

    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y + self.height / 2

    @property
    def area(self) -> float:
        return max(1e-6, self.width) * max(1e-6, self.height)

    def as_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 6),
            "y": round(self.y, 6),
            "width": round(self.width, 6),
            "height": round(self.height, 6),
        }

    def intersection_over_union(self, other: "Box") -> float:
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.x + self.width, other.x + other.width)
        bottom = min(self.y + self.height, other.y + other.height)
        if right <= left or bottom <= top:
            return 0.0
        overlap = (right - left) * (bottom - top)
        return overlap / max(1e-6, self.area + other.area - overlap)


def parse_aspect_ratio(aspect_ratio: str) -> tuple[float, float]:
    normalized = aspect_ratio.strip().replace(":", "/")
    try:
        width, height = (float(part) for part in normalized.split("/", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}") from exc
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}")
    return width, height


def output_dimensions(aspect_ratio: str, preferred: tuple[int, int] | None = None) -> tuple[int, int]:
    if preferred:
        width, height = preferred
        target_width, target_height = parse_aspect_ratio(aspect_ratio)
        if not math.isclose(width / height, target_width / target_height, rel_tol=1e-6):
            raise ValueError(f"Preferred dimensions do not match {aspect_ratio}")
        return width, height
    if aspect_ratio not in DEFAULT_OUTPUT_DIMENSIONS:
        raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}")
    return DEFAULT_OUTPUT_DIMENSIONS[aspect_ratio]


def normalize_box(
    box: dict[str, Any] | Box | None,
    frame_width: int | float | None = None,
    frame_height: int | float | None = None,
) -> Box | None:
    """Coerce a raw box into a clamped, normalised :class:`Box`.

    Accepts either normalised or pixel coordinates. Pixel input is detected by
    a value exceeding 1.0, and converted using the frame size carried on the box
    itself when explicit dimensions are not supplied.
    """
    if box is None:
        return None
    if isinstance(box, Box):
        source: dict[str, Any] = box.as_dict()
    elif isinstance(box, dict):
        source = box
    else:
        return None

    try:
        x = float(source.get("x", 0.0))
        y = float(source.get("y", 0.0))
        width = float(source.get("width", 0.0))
        height = float(source.get("height", 0.0))
    except (TypeError, ValueError):
        return None

    fw = float(frame_width or source.get("frame_width") or 0.0)
    fh = float(frame_height or source.get("frame_height") or 0.0)
    if fw > 0 and max(x, width) > 1.0:
        x, width = x / fw, width / fw
    if fh > 0 and max(y, height) > 1.0:
        y, height = y / fh, height / fh

    x = min(1.0, max(0.0, x))
    y = min(1.0, max(0.0, y))
    width = min(1.0 - x, max(0.0, width))
    height = min(1.0 - y, max(0.0, height))
    if width <= 0.0 or height <= 0.0:
        return None
    return Box(x=x, y=y, width=width, height=height)


def target_crop_size(source_width: int, source_height: int, aspect_ratio: str) -> tuple[int, int]:
    """Largest even-sized window of ``aspect_ratio`` that fits the source frame."""
    target_width_ratio, target_height_ratio = parse_aspect_ratio(aspect_ratio)
    source_ratio = source_width / max(1, source_height)
    target_ratio = target_width_ratio / max(1e-6, target_height_ratio)
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = int(round(crop_height * target_ratio))
    else:
        crop_width = source_width
        crop_height = int(round(crop_width / target_ratio))
    crop_width = min(crop_width, source_width)
    crop_height = min(crop_height, source_height)
    crop_width -= crop_width % 2
    crop_height -= crop_height % 2
    return max(2, crop_width), max(2, crop_height)


def crop_around(
    center_x: float,
    center_y: float,
    source_width: int,
    source_height: int,
    aspect_ratio: str,
) -> Box:
    """Crop window of ``aspect_ratio`` centred on a normalised point.

    The returned box is top-left origin. Centring is done in pixels and then
    clamped to the frame, so a subject near an edge yields a crop flush with
    that edge rather than one that runs off it.
    """
    crop_w, crop_h = target_crop_size(source_width, source_height, aspect_ratio)
    cx = min(1.0, max(0.0, center_x)) * source_width
    cy = min(1.0, max(0.0, center_y)) * source_height
    left = max(0.0, min(float(source_width - crop_w), cx - crop_w / 2))
    top = max(0.0, min(float(source_height - crop_h), cy - crop_h / 2))
    return Box(
        x=left / source_width,
        y=top / source_height,
        width=crop_w / source_width,
        height=crop_h / source_height,
    )


def crop_covering(
    boxes: list[Box],
    source_width: int,
    source_height: int,
    aspect_ratio: str,
) -> Box:
    """Crop centred on the union of ``boxes``, so no subject is cut off."""
    if not boxes:
        return crop_around(0.5, 0.5, source_width, source_height, aspect_ratio)
    left = min(b.x for b in boxes)
    top = min(b.y for b in boxes)
    right = max(b.x + b.width for b in boxes)
    bottom = max(b.y + b.height for b in boxes)
    return crop_around(
        (left + right) / 2,
        (top + bottom) / 2,
        source_width,
        source_height,
        aspect_ratio,
    )


def union_box(boxes: list[Box]) -> Box | None:
    if not boxes:
        return None
    left = min(b.x for b in boxes)
    top = min(b.y for b in boxes)
    right = max(b.x + b.width for b in boxes)
    bottom = max(b.y + b.height for b in boxes)
    return Box(x=left, y=top, width=max(1e-6, right - left), height=max(1e-6, bottom - top))


# FFmpeg's expression evaluator rejects graphs beyond a few thousand characters
# ("Failed to configure input pad on Parsed_crop_0"), which silently demoted long
# clips to a centred crop. Measured failure begins between 2.4k and 3.7k chars, so
# the path is subsampled to stay well inside that.
MAX_CROP_EXPRESSION_CHARS = 2000


def _subsample_points(points: list[tuple[float, "Box"]], limit: int) -> list[tuple[float, "Box"]]:
    """Evenly thin a tracking path, always keeping the first and last point."""
    if len(points) <= limit or limit < 2:
        return points
    step = (len(points) - 1) / (limit - 1)
    thinned = [points[min(len(points) - 1, round(i * step))] for i in range(limit)]
    thinned[-1] = points[-1]
    deduped: list[tuple[float, "Box"]] = []
    for point in thinned:
        if not deduped or point[0] > deduped[-1][0]:
            deduped.append(point)
    return deduped


def crop_tracking_expressions(
    crop_tracking: list[dict[str, Any]],
    source_width: int,
    source_height: int,
    crop_width: int,
    crop_height: int,
) -> tuple[str, str]:
    """Build FFmpeg ``crop`` x/y expressions that pan between tracking points.

    Timestamps must already be relative to the start of the output clip.

    The path is expressed as a flat sum of clamped linear ramps rather than
    nested ``if()`` calls:

        x(t) = x0 + sum_i slope_i * clip(t - t_i, 0, dt_i)

    Each term contributes its segment's change once ``t`` passes it and nothing
    before, which reproduces piecewise-linear interpolation with no nesting. The
    nested form grew one level per point and FFmpeg failed to parse it beyond
    roughly a minute of tracking, falling back to a centred crop.
    """
    max_x = max(0, source_width - crop_width)
    max_y = max(0, source_height - crop_height)
    static = (str(max_x // 2), str(max_y // 2))
    if not crop_tracking:
        return static

    points: list[tuple[float, Box]] = []
    for item in crop_tracking:
        box = normalize_box(item.get("bbox"))
        if box is not None:
            points.append((float(item.get("timestamp", 0.0)), box))
    if not points:
        return static
    points.sort(key=lambda item: item[0])

    # Roughly 31 characters per segment term; keep both axes inside the budget.
    max_points = max(2, MAX_CROP_EXPRESSION_CHARS // 31)
    if len(points) > max_points:
        original = len(points)
        points = _subsample_points(points, max_points)
        log.info(
            "Subsampled crop tracking from %d to %d point(s) to stay within FFmpeg's expression limit",
            original, len(points),
        )

    def axis_expression(axis: str) -> str:
        scale = source_width if axis == "x" else source_height
        limit = max_x if axis == "x" else max_y

        def value_at(box: Box) -> float:
            return (box.x if axis == "x" else box.y) * scale

        base = value_at(points[0][1])
        if len(points) == 1 or limit <= 0:
            return f"clip({base:.3f},0,{limit})"

        terms: list[str] = [f"{base:.3f}"]
        for (start_time, start_box), (end_time, end_box) in zip(points, points[1:]):
            span = max(end_time - start_time, 1e-3)
            delta = value_at(end_box) - value_at(start_box)
            if abs(delta) < 1e-6:
                continue
            slope = delta / span
            terms.append(f"{slope:+.5f}*clip(t-{start_time:.3f},0,{span:.3f})")

        return f"clip({''.join(terms)},0,{limit})"

    return axis_expression("x"), axis_expression("y")
