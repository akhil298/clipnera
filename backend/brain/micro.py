"""Micro-edits: a resolved item plus modifiers in, Timeline ops out, with no model call.

"Make the title bigger" becomes one update_item. Anything the table can't express, or that
grows past the P5 limits (TODO 5.5.2), escalates to a plan instead of guessing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from brain.modifiers import Modifier
from editor.ops import ItemPatch, MoveItem, Op, SetProject, TransformPatch, TrimItem, UpdateItem
from editor.timeline import ClipItem, GraphicItem, Item, MusicItem, SfxItem, TextItem, Timeline

# P5: what still counts as a micro-edit.
MAX_OPS = 3
MAX_CLIPS = 1
CREDITS = 1

SCALE_RANGE = (0.1, 10.0)
VOLUME_RANGE = (0.0, 2.0)
GAIN_RANGE = (-60.0, 12.0)
SPEED_RANGE = (0.25, 4.0)
POSITION_RANGE = (-1.0, 2.0)


class Escalate(Exception):
    """This can't be done as a micro-edit; plan it instead. The message says why."""


@dataclass(frozen=True)
class MicroEdit:
    ops: list[Any]
    label: str
    credits: int = CREDITS


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    return round(min(bounds[1], max(bounds[0], value)), 4)


def build(timeline: Timeline, item: Item | None, modifiers: Sequence[Modifier], prompt: str) -> MicroEdit:
    """Ops for ``modifiers`` on ``item`` (None for project-wide changes such as the look)."""
    if not modifiers:
        raise Escalate("No small change to make was found in that request.")
    ops: list[Any] = []
    patch: dict[str, Any] = {}
    transform: dict[str, float] = {}
    for modifier in modifiers:
        if modifier.prop == "look":
            ops.append(SetProject(op="set_project", look=str(modifier.value)))
            continue
        if item is None:
            raise Escalate(f"Say which item to change ({modifier.prop.replace('_', ' ')}).")
        _apply(timeline, item, modifier, patch, transform, ops)
    if transform:
        patch["transform"] = TransformPatch(**transform)
    if patch and item is not None:
        ops.insert(0, UpdateItem(op="update_item", item=item.id, patch=ItemPatch(**patch)))
    check_p5(timeline, ops)
    return MicroEdit(ops=ops, label=prompt.strip()[:80])


def _apply(timeline: Timeline, item: Item, modifier: Modifier, patch: dict[str, Any],
           transform: dict[str, float], ops: list[Any]) -> None:
    prop, value = modifier.prop, modifier.value
    if prop in ("scale", "x", "y"):
        if not isinstance(item, (ClipItem, TextItem)):
            raise Escalate(f"A {item.type} has no size or position on screen.")
        current = getattr(item.transform, prop)
        bounds = SCALE_RANGE if prop == "scale" else POSITION_RANGE
        transform[prop] = _clamp(current * value if modifier.mode == "mul" else current + value, bounds)
    elif prop == "volume_db":
        _volume(item, modifier, patch)
    elif prop == "speed":
        if not isinstance(item, ClipItem):
            raise Escalate("Only clips have a speed.")
        patch["speed"] = _clamp(item.speed * float(value), SPEED_RANGE)
    elif prop == "length":
        _length(timeline, item, float(value), patch, ops)
    elif prop == "at_seconds":
        ops.append(MoveItem(op="move_item", item=item.id, at=max(0, item.at + round(float(value) * timeline.fps))))


def _volume(item: Item, modifier: Modifier, patch: dict[str, Any]) -> None:
    mute = modifier.mode == "set" and modifier.value == "mute"
    if isinstance(item, ClipItem):
        if mute or modifier.mode == "set":
            patch["volume"] = 0.0 if mute else 1.0
        else:
            patch["volume"] = _clamp(max(item.volume, 0.01) * 10 ** (float(modifier.value) / 20), VOLUME_RANGE)
    elif isinstance(item, (MusicItem, SfxItem)):
        if mute or modifier.mode == "set":
            patch["gain_db"] = GAIN_RANGE[0] if mute else 0.0
        else:
            patch["gain_db"] = _clamp(item.gain_db + float(modifier.value), GAIN_RANGE)
    else:
        raise Escalate(f"A {item.type} has no sound to make louder or quieter.")


def _length(timeline: Timeline, item: Item, factor: float, patch: dict[str, Any], ops: list[Any]) -> None:
    if isinstance(item, ClipItem):
        asset = timeline.assets[item.asset]
        span = item.src_out - item.src_in
        wanted = max(1, round(span * factor))
        src_out = item.src_in + wanted
        if asset.kind != "image":
            src_out = min(src_out, asset.frames)
        if src_out == item.src_out:
            raise Escalate("That clip can't get any longer: it already plays to the end of its footage.")
        ops.append(TrimItem(op="trim_item", item=item.id, src_out=src_out))
    elif isinstance(item, (TextItem, MusicItem, SfxItem, GraphicItem)):
        patch["dur"] = max(1, round(item.dur * factor))
    else:  # pragma: no cover - every item type is handled above
        raise Escalate(f"A {item.type} has no length to change.")


def check_p5(timeline: Timeline, ops: Sequence[Op | Any]) -> None:
    """A micro-edit is at most 3 ops on at most 1 clip, with nothing premium (TODO 5.5.2)."""
    if len(ops) > MAX_OPS:
        raise Escalate(f"That's {len(ops)} changes; more than {MAX_OPS} goes through a plan.")
    clips = {getattr(op, "item", None) for op in ops if getattr(op, "item", None)}
    clip_ids = {item_id for item_id in clips if _is_clip(timeline, item_id)}
    if len(clip_ids) > MAX_CLIPS:
        raise Escalate("That touches more than one clip; it goes through a plan.")


def _is_clip(timeline: Timeline, item_id: str) -> bool:
    try:
        return isinstance(timeline.find(item_id)[1], ClipItem)
    except Exception:
        return False
