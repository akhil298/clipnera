"""Keyframed values as FFmpeg expressions, so a zoom or a pan moves frame by frame.

A point is (seconds from the item's start, value, ease). The value is held before the first
point and after the last; between two points it follows the ease of the point it moves towards
(the Timeline's rule, and the Mac editor's preview: desktop/src/renderer/src/player/framing.ts).
"""

from __future__ import annotations

Point = tuple[float, float, str]


def _eased(ease: str, p: str) -> str:
    if ease == "in":
        return f"{p}*{p}"
    if ease == "out":
        return f"{p}*(2-{p})"
    if ease == "in_out":
        return f"if(lt({p},0.5),2*{p}*{p},1-2*(1-{p})*(1-{p}))"
    return p


def curve(points: list[Point], var: str) -> str:
    """An expression in ``var`` (seconds) for the value moving through ``points``."""
    points = sorted(points)
    expr = f"{points[-1][1]:.4f}"
    for (t0, v0, _), (t1, v1, ease) in reversed(list(zip(points, points[1:]))):
        if t1 <= t0:
            continue
        p = f"(({var}-{t0:.4f})/{t1 - t0:.4f})"
        expr = f"if(lt({var},{t1:.4f}),{v0:.4f}+{v1 - v0:.4f}*{_eased(ease, p)},{expr})"
    return f"if(lt({var},{points[0][0]:.4f}),{points[0][1]:.4f},{expr})"


def moves(points: list[Point] | None) -> bool:
    """Whether the points change the value at all."""
    return bool(points) and len({round(v, 4) for _, v, _ in points}) > 1
