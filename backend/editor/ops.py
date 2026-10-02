"""Operations: the only way a Timeline changes.

The user's hand edits and the agent's edits are the same operations, so one
undo history covers both and the server can log, replay and rebase them.
``apply_ops`` is pure: it returns a new Timeline and leaves the input alone.
Mirrored by applyOps in frontend/lib/editor/timeline.ts.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from editor.timeline import (
    Asset,
    Captions,
    ClipItem,
    Frame,
    Id,
    Item,
    Keyframe,
    KeyframeProp,
    Marker,
    Timeline,
    TimelineError,
    Track,
    TrackKind,
    Transition,
    check,
    to_frames,
)


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddItem(_Op):
    op: Literal["add_item"]
    track: Id
    item: Item


class RemoveItem(_Op):
    op: Literal["remove_item"]
    item: Id
    # Close the gap by pulling later items on the same track left.
    ripple: bool = False


class MoveItem(_Op):
    op: Literal["move_item"]
    item: Id
    at: Frame
    track: Id | None = None


class TrimItem(_Op):
    """Change which source frames a clip plays; its start on the timeline stays put."""

    op: Literal["trim_item"]
    item: Id
    src_in: Frame | None = None
    src_out: int | None = Field(None, ge=1)


class SplitItem(_Op):
    op: Literal["split_item"]
    item: Id
    # Timeline frame to cut at, strictly inside the clip.
    at: Frame
    new_id: Id


class TransformPatch(_Op):
    x: float | None = None
    y: float | None = None
    scale: float | None = None
    rotation: float | None = None


class ItemPatch(_Op):
    """Fields to change on one item; a field the item doesn't have is refused."""

    speed: float | None = None
    volume: float | None = None
    transform: TransformPatch | None = None
    keyframes: dict[KeyframeProp, list[Keyframe]] | None = None
    transition_in: Transition | None = None
    text: str | None = None
    style: str | None = None
    dur: int | None = None
    offset: int | None = None
    gain_db: float | None = None
    duck: bool | None = None


class UpdateItem(_Op):
    op: Literal["update_item"]
    item: Id
    patch: ItemPatch


class ReplaceAsset(_Op):
    """Swap what a clip shows (a B-roll swap) and keep its timing."""

    op: Literal["replace_asset"]
    item: Id
    asset: Id


class AddTrack(_Op):
    op: Literal["add_track"]
    id: Id
    kind: TrackKind


class AddAsset(_Op):
    op: Literal["add_asset"]
    asset: Asset


class SetCaptions(_Op):
    op: Literal["set_captions"]
    enabled: bool | None = None
    style: str | None = Field(None, min_length=1, max_length=60)
    language: str | None = Field(None, min_length=2, max_length=20)
    follow: Id | None = None


class SetProject(_Op):
    op: Literal["set_project"]
    look: str | None = Field(None, min_length=1, max_length=40)
    width: int | None = Field(None, ge=16, le=4096)
    height: int | None = Field(None, ge=16, le=4096)


class AddMarker(_Op):
    op: Literal["add_marker"]
    marker: Marker


class RemoveMarker(_Op):
    op: Literal["remove_marker"]
    f: Frame


Op = Annotated[
    AddTrack | AddItem | RemoveItem | MoveItem | TrimItem | SplitItem | UpdateItem | ReplaceAsset | AddAsset
    | SetCaptions | SetProject | AddMarker | RemoveMarker,
    Field(discriminator="op"),
]


def apply_ops(timeline: Timeline, ops: Sequence[Op]) -> Timeline:
    """Apply ``ops`` in order to a copy of ``timeline``; nothing changes if any op fails.

    The error names the failing op's position in ``extra["op_index"]``, so the
    agent can be told exactly which edit to fix.
    """
    doc = timeline.model_copy(deep=True)
    for index, op in enumerate(ops):
        try:
            _APPLY[op.op](doc, op)
            for track in doc.tracks:
                track.items.sort(key=lambda item: item.at)
            check(doc)
        except TimelineError as exc:
            exc.extra["op_index"] = index
            raise
    return doc


def _clip(doc: Timeline, item_id: str) -> ClipItem:
    _, item = doc.find(item_id)
    if not isinstance(item, ClipItem):
        raise TimelineError("WRONG_ITEM_TYPE", f"{item_id} is a {item.type}, not a clip.")
    return item


def _add_item(doc: Timeline, op: AddItem) -> None:
    doc.track(op.track).items.append(op.item.model_copy(deep=True))


def _remove_item(doc: Timeline, op: RemoveItem) -> None:
    track, item = doc.find(op.item)
    track.items.remove(item)
    if op.ripple:
        for later in track.items:
            if later.at >= item.end:
                later.at -= item.frames


def _move_item(doc: Timeline, op: MoveItem) -> None:
    track, item = doc.find(op.item)
    item.at = op.at
    if op.track is not None and op.track != track.id:
        target = doc.track(op.track)
        track.items.remove(item)
        target.items.append(item)


def _trim_item(doc: Timeline, op: TrimItem) -> None:
    clip = _clip(doc, op.item)
    if op.src_in is not None:
        clip.src_in = op.src_in
    if op.src_out is not None:
        clip.src_out = op.src_out
    _drop_keyframes_after(clip)


def _split_item(doc: Timeline, op: SplitItem) -> None:
    clip = _clip(doc, op.item)
    offset = op.at - clip.at
    if not 0 < offset < clip.frames:
        raise TimelineError("OUT_OF_RANGE", f"Frame {op.at} is not inside {clip.id}.")
    cut = clip.src_in + to_frames(offset * clip.speed)
    left_keys, right_keys = _split_keyframes(clip.keyframes, offset)
    right = clip.model_copy(deep=True, update={
        "id": op.new_id, "at": op.at, "src_in": cut, "transition_in": None, "keyframes": right_keys,
    })
    clip.src_out, clip.keyframes = cut, left_keys
    doc.find(clip.id)[0].items.append(right)


def _split_keyframes(keyframes: dict[str, list[Keyframe]], offset: int) -> tuple[dict, dict]:
    """Keyframes before ``offset`` stay on the left piece; the rest move to the right, re-based to its start."""
    left: dict[str, list[Keyframe]] = {}
    right: dict[str, list[Keyframe]] = {}
    for prop, points in keyframes.items():
        before = [p for p in points if p.f < offset]
        after = [p.model_copy(update={"f": p.f - offset}) for p in points if p.f >= offset]
        if before:
            left[prop] = before
        if after:
            right[prop] = after
    return left, right


def _update_item(doc: Timeline, op: UpdateItem) -> None:
    track, item = doc.find(op.item)
    patch = op.patch.model_dump(exclude_none=True)
    if "transform" in patch:
        if not hasattr(item, "transform"):
            raise TimelineError("BAD_PATCH", f"A {item.type} has no transform.")
        patch["transform"] = {**item.transform.model_dump(), **patch["transform"]}
    try:
        updated = type(item).model_validate({**item.model_dump(), **patch})
    except ValidationError as exc:
        raise TimelineError("BAD_PATCH", f"That change doesn't fit {item.id}: {_first_error(exc)}") from exc
    if isinstance(updated, ClipItem):
        _drop_keyframes_after(updated)
    track.items[track.items.index(item)] = updated


def _replace_asset(doc: Timeline, op: ReplaceAsset) -> None:
    clip = _clip(doc, op.item)
    clip.asset = op.asset
    length = clip.src_out - clip.src_in
    clip.src_in, clip.src_out = 0, length


def _add_track(doc: Timeline, op: AddTrack) -> None:
    doc.tracks.append(Track(id=op.id, kind=op.kind))


def _add_asset(doc: Timeline, op: AddAsset) -> None:
    if op.asset.id in doc.assets:
        raise TimelineError("DUPLICATE_ID", f"The project already has an asset {op.asset.id}.")
    doc.assets[op.asset.id] = op.asset.model_copy(deep=True)


def _set_captions(doc: Timeline, op: SetCaptions) -> None:
    changes = op.model_dump(exclude_none=True, exclude={"op"})
    if doc.captions is None:
        if "follow" not in changes:
            raise TimelineError("UNKNOWN_TRACK", "Say which track the captions follow.")
        doc.captions = Captions.model_validate(changes)
    else:
        doc.captions = doc.captions.model_copy(update=changes)


def _set_project(doc: Timeline, op: SetProject) -> None:
    for field, value in op.model_dump(exclude_none=True, exclude={"op"}).items():
        setattr(doc, field, value)


def _add_marker(doc: Timeline, op: AddMarker) -> None:
    doc.markers = sorted([m for m in doc.markers if m.f != op.marker.f] + [op.marker], key=lambda m: m.f)


def _remove_marker(doc: Timeline, op: RemoveMarker) -> None:
    doc.markers = [m for m in doc.markers if m.f != op.f]


def _drop_keyframes_after(clip: ClipItem) -> None:
    """Keyframes past a shortened clip's end no longer mean anything."""
    length = clip.frames
    kept = {prop: [p for p in points if p.f <= length] for prop, points in clip.keyframes.items()}
    clip.keyframes = {prop: points for prop, points in kept.items() if points}


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    field = ".".join(str(part) for part in error["loc"])
    return f"{field}: {error['msg']}" if field else error["msg"]


_APPLY: dict[str, Callable[[Timeline, Any], None]] = {
    "add_track": _add_track,
    "add_item": _add_item,
    "remove_item": _remove_item,
    "move_item": _move_item,
    "trim_item": _trim_item,
    "split_item": _split_item,
    "update_item": _update_item,
    "replace_asset": _replace_asset,
    "add_asset": _add_asset,
    "set_captions": _set_captions,
    "set_project": _set_project,
    "add_marker": _add_marker,
    "remove_marker": _remove_marker,
}
