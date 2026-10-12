"""Operations: the only way a Timeline changes.

The user's hand edits and the agent's edits are the same operations, so one
undo history covers both and the server can log, replay and rebase them.
``apply_ops`` is pure: it returns a new Timeline and leaves the input alone.
Mirrored by applyOps in frontend/lib/editor/timeline.ts.

``apply_tracked`` also returns each batch's inverse (the ops that put the
Timeline back, for undo) and which fields of which items it changed (for
human ownership and rebasing). Inverses may use two internal ops,
``restore_item`` and ``restore_fields``, that clients can't send.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from editor.timeline import (
    Asset,
    Captions,
    ClipItem,
    Extra,
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
    # Replaces the item's studio-only data whole.
    extra: Extra | None = None


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


class UpdateTrack(_Op):
    op: Literal["update_track"]
    track: Id
    muted: bool | None = None
    hidden: bool | None = None
    extra: Extra | None = None


class RemoveTrack(_Op):
    """Remove an empty track."""

    op: Literal["remove_track"]
    track: Id


class ReorderTracks(_Op):
    """Put the tracks in this order, top of the stack first; every track named once."""

    op: Literal["reorder_tracks"]
    order: list[Id]


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
    AddTrack | UpdateTrack | RemoveTrack | ReorderTracks | AddItem | RemoveItem | MoveItem | TrimItem | SplitItem
    | UpdateItem | ReplaceAsset | AddAsset | SetCaptions | SetProject | AddMarker | RemoveMarker,
    Field(discriminator="op"),
]


class RestoreItem(_Op):
    """Internal (undo): put an item back exactly as it was, on its track, adding it if it is gone."""

    op: Literal["restore_item"]
    track: Id
    item: Item


# The Timeline fields restore_fields may set.
RESTORABLE_FIELDS = frozenset({"assets", "captions", "markers", "look", "width", "height"})


class RestoreFields(_Op):
    """Internal (undo): put Timeline-level fields back as they were (captions may go back to none)."""

    op: Literal["restore_fields"]
    fields: dict[str, Any]


# Every op a stored batch may hold: what clients send, plus the internal undo ops.
AnyOp = Annotated[
    AddTrack | UpdateTrack | RemoveTrack | ReorderTracks | AddItem | RemoveItem | MoveItem | TrimItem | SplitItem
    | UpdateItem | ReplaceAsset | AddAsset | SetCaptions | SetProject | AddMarker | RemoveMarker
    | RestoreItem | RestoreFields,
    Field(discriminator="op"),
]
STORED_OPS = TypeAdapter(list[AnyOp])

# Item id -> the fields an op changed; "*" means the whole item (made, removed or restored).
Touched = dict[str, set[str]]
WHOLE_ITEM = "*"


@dataclass
class Applied:
    timeline: Timeline
    # Ops that turn ``timeline`` back into the input, in order.
    inverse: list[Any]
    touched: Touched


def apply_ops(timeline: Timeline, ops: Sequence[Any]) -> Timeline:
    """Apply ``ops`` in order to a copy of ``timeline``; nothing changes if any op fails.

    The error names the failing op's position in ``extra["op_index"]``, so the
    agent can be told exactly which edit to fix.
    """
    return apply_tracked(timeline, ops).timeline


def apply_tracked(timeline: Timeline, ops: Sequence[Any]) -> Applied:
    """``apply_ops``, plus the batch's inverse and what it touched."""
    doc = timeline.model_copy(deep=True)
    parts: list[list[Any]] = []
    touched: Touched = {}
    for index, op in enumerate(ops):
        try:
            # Both read the Timeline as it is before the op.
            parts.append(invert(doc, op))
            for item_id, fields in touches(doc, op).items():
                touched.setdefault(item_id, set()).update(fields)
            _APPLY[op.op](doc, op)
            for track in doc.tracks:
                track.items.sort(key=lambda item: item.at)
            check(doc)
        except TimelineError as exc:
            exc.extra["op_index"] = index
            raise
    return Applied(doc, [inverse for part in reversed(parts) for inverse in part], touched)


def invert(before: Timeline, op: Any) -> list[Any]:
    """The ops that undo ``op`` applied to ``before``."""
    match op:
        case AddTrack():
            return [RemoveTrack(op="remove_track", track=op.id)]
        case UpdateTrack():
            track = before.track(op.track)
            return [UpdateTrack(op="update_track", track=track.id, muted=track.muted, hidden=track.hidden,
                                extra=track.extra)]
        case RemoveTrack():
            track = before.track(op.track)
            return [
                AddTrack(op="add_track", id=track.id, kind=track.kind),
                UpdateTrack(op="update_track", track=track.id, muted=track.muted, hidden=track.hidden,
                            extra=track.extra),
                ReorderTracks(op="reorder_tracks", order=[t.id for t in before.tracks]),
            ]
        case ReorderTracks():
            return [ReorderTracks(op="reorder_tracks", order=[t.id for t in before.tracks])]
        case AddItem():
            return [RemoveItem(op="remove_item", item=op.item.id)]
        case RemoveItem():
            track, item = before.find(op.item)
            # Items a ripple pulled left go back right, last first, so none lands on another.
            later = sorted((i for i in track.items if op.ripple and i.at >= item.end), key=lambda i: -i.at)
            return [*(MoveItem(op="move_item", item=i.id, at=i.at) for i in later), _restore(track, item)]
        case MoveItem():
            track, item = before.find(op.item)
            moved_track = op.track is not None and op.track != track.id
            return [MoveItem(op="move_item", item=item.id, at=item.at, track=track.id if moved_track else None)]
        case TrimItem() | UpdateItem() | ReplaceAsset():
            return [_restore(*before.find(op.item))]
        case SplitItem():
            return [RemoveItem(op="remove_item", item=op.new_id), _restore(*before.find(op.item))]
        case RestoreItem():
            try:
                return [_restore(*before.find(op.item.id))]
            except TimelineError:
                return [RemoveItem(op="remove_item", item=op.item.id)]
        case AddAsset():
            return [_restore_fields(before, "assets")]
        case SetCaptions():
            return [_restore_fields(before, "captions")]
        case SetProject():
            return [_restore_fields(before, "look", "width", "height")]
        case AddMarker() | RemoveMarker():
            return [_restore_fields(before, "markers")]
        case RestoreFields():
            return [_restore_fields(before, *op.fields)]
    raise TimelineError("UNKNOWN_OP", f"There is no operation {getattr(op, 'op', op)!r}.")


def _restore(track: Track, item: Any) -> RestoreItem:
    return RestoreItem(op="restore_item", track=track.id, item=item.model_copy(deep=True))


def _restore_fields(before: Timeline, *names: str) -> RestoreFields:
    dumped = before.model_dump(mode="json", include=set(names))
    return RestoreFields(op="restore_fields", fields={name: dumped[name] for name in names})


def touches(before: Timeline, op: Any) -> Touched:
    """Which fields of which items ``op`` changes, read from the Timeline before it."""
    match op:
        case AddItem():
            return {op.item.id: {WHOLE_ITEM}}
        case RemoveItem():
            track, item = before.find(op.item)
            shifted = {i.id: {"at"} for i in track.items if op.ripple and i.at >= item.end}
            return {**shifted, item.id: {WHOLE_ITEM}}
        case MoveItem():
            track, _ = before.find(op.item)
            return {op.item: {"at", "track"} if op.track not in (None, track.id) else {"at"}}
        case TrimItem():
            return {op.item: {name for name in ("src_in", "src_out") if getattr(op, name) is not None}}
        case SplitItem():
            return {op.item: {"src_out", "keyframes"}, op.new_id: {WHOLE_ITEM}}
        case UpdateItem():
            return {op.item: set(op.patch.model_dump(exclude_none=True))}
        case ReplaceAsset():
            return {op.item: {"asset", "src_in", "src_out"}}
        case RestoreItem():
            return {op.item.id: {WHOLE_ITEM}}
    return {}


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


def _update_track(doc: Timeline, op: UpdateTrack) -> None:
    track = doc.track(op.track)
    for field, value in op.model_dump(exclude_none=True, exclude={"op", "track"}).items():
        setattr(track, field, value)


def _remove_track(doc: Timeline, op: RemoveTrack) -> None:
    track = doc.track(op.track)
    if track.items:
        raise TimelineError("TRACK_NOT_EMPTY", f"Track {track.id} still has {len(track.items)} items on it.")
    if doc.captions is not None and doc.captions.follow == track.id:
        raise TimelineError("TRACK_IN_USE", f"The captions follow track {track.id}.")
    doc.tracks.remove(track)


def _reorder_tracks(doc: Timeline, op: ReorderTracks) -> None:
    if sorted(op.order) != sorted(track.id for track in doc.tracks):
        raise TimelineError("BAD_ORDER", "Name every track exactly once to reorder them.")
    doc.tracks.sort(key=lambda track: op.order.index(track.id))


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


def _restore_item(doc: Timeline, op: RestoreItem) -> None:
    try:
        track, item = doc.find(op.item.id)
        track.items.remove(item)
    except TimelineError:
        pass
    doc.track(op.track).items.append(op.item.model_copy(deep=True))


def _restore_fields_op(doc: Timeline, op: RestoreFields) -> None:
    unknown = set(op.fields) - RESTORABLE_FIELDS
    if unknown:
        raise TimelineError("BAD_PATCH", f"These fields can't be restored: {sorted(unknown)}.")
    restored = Timeline.model_validate({**doc.model_dump(mode="json"), **op.fields})
    for name in op.fields:
        setattr(doc, name, getattr(restored, name))


_APPLY: dict[str, Callable[[Timeline, Any], None]] = {
    "add_track": _add_track,
    "update_track": _update_track,
    "remove_track": _remove_track,
    "reorder_tracks": _reorder_tracks,
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
    "restore_item": _restore_item,
    "restore_fields": _restore_fields_op,
}
