"""A clip's motion plan laid onto its rendered file, ready to burn.

The plan is in source seconds; the render plays ``[hook][bridge][body]``. Cues
move onto that timeline (body cues after the hook and its bridge), the cut's
layout stretches move with them, and what comes out is the graphics script,
the sounds and where captions step aside.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clip_generation.hook import Hook, Span, source_to_cut
from motion.graphics import LayoutSpan, Placed, graphics_ass
from motion.plan import QUIETS_CAPTIONS, MotionPlan
from motion.sound import Sound, sounds_for


@dataclass(frozen=True)
class MotionSource:
    """What a render needs to draw a clip's graphics: its plan and the cut's
    layout stretches (``output_formats[ratio]["frames"]``)."""

    plan: MotionPlan | None
    frames: list[dict[str, Any]] | None = None


@dataclass
class Overlay:
    ass: str
    sounds: list[Sound] = field(default_factory=list)
    # (start, end) seconds of the output where captions step aside.
    quiet: list[tuple[float, float]] = field(default_factory=list)


def build_overlay(
    plan: MotionPlan | None,
    frames: list[dict[str, Any]] | None,
    clip_start: float,
    clip_end: float,
    hook: Hook | None,
    spans: list[Span] | None,
    gap: float,
    width: int,
    height: int,
    title_seconds: float,
) -> Overlay | None:
    """The overlay for one render, or ``None`` when the plan draws nothing there."""
    if plan is None or not plan.cues:
        return None
    shift = gap if hook else 0.0
    placed: list[Placed] = []
    for cue in plan.cues:
        start = source_to_cut(cue.start, clip_start, clip_end, hook, spans)
        end = source_to_cut(min(cue.end, _body_end(clip_start, clip_end, spans)), clip_start, clip_end, hook, spans)
        beats = [source_to_cut(beat, clip_start, clip_end, hook, spans) for beat in cue.beats]
        if start is None or end is None or end - start < 0.5 or any(beat is None for beat in beats):
            continue  # Part of it was cut out of the clip: a half-shown graphic is worse than none.
        placed.append(Placed(cue.kind, start + shift, end + shift, cue.data, [beat + shift for beat in beats]))
    if not placed:
        return None
    layouts = [_shifted(LayoutSpan.from_stored(item), hook, shift) for item in frames or [] if _readable(item)]
    drawn: list[Placed] = []
    ass = graphics_ass(placed, layouts, width, height, title_seconds, drawn=drawn)
    if ass is None:
        return None
    return Overlay(
        ass=ass,
        sounds=sounds_for(drawn),
        quiet=[(cue.start, cue.end) for cue in drawn if cue.kind in QUIETS_CAPTIONS],
    )


def _body_end(clip_start: float, clip_end: float, spans: list[Span] | None) -> float:
    return spans[-1][1] if spans else clip_end


def _shifted(span: LayoutSpan, hook: Hook | None, shift: float) -> LayoutSpan:
    """A stretch of the cut moved onto the output: everything after the teaser moves past the bridge."""
    if hook is None or span.start < hook.duration - 1e-3:
        return span
    return LayoutSpan(span.start + shift, span.end + shift, span.kind, span.top, span.faces)


def _readable(item: Any) -> bool:
    return isinstance(item, dict) and {"start", "end", "kind"} <= item.keys()
