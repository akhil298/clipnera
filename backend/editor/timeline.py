"""Timeline v1: the one document the editor, the agent, the preview and the renderer share.

Time is whole frames at the timeline's fps, never float seconds, so the preview,
the render and an XML export can't drift apart. Items sit on tracks; a clip
plays ``src_in``..``src_out`` of an asset (in timeline frames) from ``at``.

Pydantic checks each field; ``check`` enforces the rules that span the
document (ids, track kinds, overlaps, ranges). Mirrored field for field by
frontend/lib/editor/timeline.ts, and the fixtures in editor/fixtures keep the
two in step.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.exceptions import CustomException
from subtitle_styling.templates import DEFAULT_STYLE

Frame = Annotated[int, Field(ge=0)]
Id = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")]
TrackKind = Literal["video", "overlay", "text", "audio", "graphic"]
KeyframeProp = Literal["x", "y", "scale", "rotation", "opacity"]

# Which item types each kind of track holds.
TRACK_ITEMS: dict[str, frozenset[str]] = {
    "video": frozenset({"clip"}),
    "overlay": frozenset({"clip"}),
    "text": frozenset({"text"}),
    "audio": frozenset({"clip", "music", "sfx"}),
    "graphic": frozenset({"graphic"}),
}

# What the studio (OpenCut) keeps that Timeline v1 has no field for: masks,
# effects, animations, text styling, a track's name. Carried untouched, so a
# project opened in the studio comes back as it was left.
Extra = dict[str, Any]


class TimelineError(CustomException):
    """A Timeline or an operation broke a rule; ``code`` says which one."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message=message, code=code, status_code=422)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Asset(_Strict):
    id: Id
    kind: Literal["video", "image", "audio"]
    key: str = Field(min_length=1, max_length=500)
    proxy: str | None = Field(None, max_length=500)
    # Length in timeline frames; an image is 1 frame and stretches to any length.
    frames: int = Field(ge=1)
    width: int | None = Field(None, ge=1)
    height: int | None = Field(None, ge=1)
    has_audio: bool = False


class Transform(_Strict):
    """Placement as shares of the frame.

    On a clip, ``x``/``y`` is the point of the source kept at the centre of the
    frame (a 9:16 crop of a wide shot follows the face) and ``scale`` zooms in
    on top of filling the frame. On text, ``x``/``y`` is where its centre sits.
    """

    x: float = Field(0.5, ge=-1, le=2)
    y: float = Field(0.5, ge=-1, le=2)
    scale: float = Field(1.0, gt=0, le=10)
    rotation: float = Field(0.0, ge=-360, le=360)


class Keyframe(_Strict):
    # Frame relative to the item's start.
    f: Frame
    v: float
    ease: Literal["linear", "in", "out", "in_out"] = "linear"


class Transition(_Strict):
    type: Literal["cut", "fade", "slide_left", "zoom"] = "cut"
    frames: int = Field(0, ge=0, le=60)


class _Item(_Strict):
    id: Id
    at: Frame
    extra: Extra = Field(default_factory=dict)

    @property
    def frames(self) -> int:
        raise NotImplementedError

    @property
    def end(self) -> int:
        return self.at + self.frames


class ClipItem(_Item):
    type: Literal["clip"]
    asset: Id
    src_in: Frame
    src_out: int = Field(ge=1)
    speed: float = Field(1.0, ge=0.25, le=4)
    volume: float = Field(1.0, ge=0, le=2)
    transform: Transform = Field(default_factory=Transform)
    keyframes: dict[KeyframeProp, list[Keyframe]] = Field(default_factory=dict)
    transition_in: Transition | None = None

    @property
    def frames(self) -> int:
        return to_frames((self.src_out - self.src_in) / self.speed)


class TextItem(_Item):
    type: Literal["text"]
    text: str = Field(min_length=1, max_length=200)
    style: str = Field(min_length=1, max_length=60)
    dur: int = Field(ge=1)
    transform: Transform = Field(default_factory=Transform)

    @property
    def frames(self) -> int:
        return self.dur


class MusicItem(_Item):
    type: Literal["music"]
    # A music library track id.
    track: str = Field(min_length=1, max_length=40)
    dur: int = Field(ge=1)
    # Frames into the track where playback starts.
    offset: Frame = 0
    gain_db: float = Field(-20.0, ge=-60, le=12)
    duck: bool = True

    @property
    def frames(self) -> int:
        return self.dur


class SfxItem(_Item):
    type: Literal["sfx"]
    name: str = Field(min_length=1, max_length=40)
    dur: int = Field(ge=1)
    gain_db: float = Field(0.0, ge=-60, le=12)

    @property
    def frames(self) -> int:
        return self.dur


class GraphicItem(_Item):
    """A sticker, graphic or effect made in the studio; what it draws lives in ``extra``."""

    type: Literal["graphic"]
    dur: int = Field(ge=1)

    @property
    def frames(self) -> int:
        return self.dur


Item = Annotated[ClipItem | TextItem | MusicItem | SfxItem | GraphicItem, Field(discriminator="type")]


class Track(_Strict):
    id: Id
    kind: TrackKind
    items: list[Item] = Field(default_factory=list)
    muted: bool = False
    hidden: bool = False
    extra: Extra = Field(default_factory=dict)


class Captions(_Strict):
    enabled: bool = True
    style: str = Field(DEFAULT_STYLE, min_length=1, max_length=60)
    # A language code or a mix ("hinglish", "tenglish"), as reels use.
    language: str = Field("en", min_length=2, max_length=20)
    # The video or audio track whose speech the captions show.
    follow: Id


class Marker(_Strict):
    f: Frame
    label: str = Field(min_length=1, max_length=80)


class Timeline(_Strict):
    version: Literal[1] = 1
    fps: Literal[24, 25, 30, 60] = 30
    width: int = Field(1080, ge=16, le=4096)
    height: int = Field(1920, ge=16, le=4096)
    look: str = Field("natural", min_length=1, max_length=40)
    assets: dict[str, Asset] = Field(default_factory=dict)
    tracks: list[Track] = Field(default_factory=list)
    captions: Captions | None = None
    markers: list[Marker] = Field(default_factory=list)

    @property
    def duration(self) -> int:
        return max((item.end for track in self.tracks for item in track.items), default=0)

    def track(self, track_id: str) -> Track:
        for track in self.tracks:
            if track.id == track_id:
                return track
        raise TimelineError("UNKNOWN_TRACK", f"There is no track {track_id}.")

    def find(self, item_id: str) -> tuple[Track, Item]:
        for track in self.tracks:
            for item in track.items:
                if item.id == item_id:
                    return track, item
        raise TimelineError("UNKNOWN_ITEM", f"There is no item {item_id}.")


def to_frames(value: float) -> int:
    """Round half up, the same as Math.round in the browser; Python's round() would round half to even."""
    return int(value + 0.5)


def check(timeline: Timeline) -> None:
    """Raise TimelineError on the first rule the Timeline breaks."""
    for key, asset in timeline.assets.items():
        if key != asset.id:
            raise TimelineError("DUPLICATE_ID", f"Asset {asset.id} is filed under {key}.")
    seen: set[str] = set()
    for track in timeline.tracks:
        if track.id in seen:
            raise TimelineError("DUPLICATE_ID", f"Two tracks are called {track.id}.")
        seen.add(track.id)
    for track in timeline.tracks:
        previous = None
        for item in sorted(track.items, key=lambda i: i.at):
            if item.id in seen:
                raise TimelineError("DUPLICATE_ID", f"Two things are called {item.id}.")
            seen.add(item.id)
            _check_item(timeline, track, item)
            if previous is not None and item.at < previous.end:
                raise TimelineError("OVERLAP", f"{item.id} overlaps {previous.id} on track {track.id}.")
            previous = item
    if timeline.captions is not None and _track_kind(timeline, timeline.captions.follow) not in ("video", "audio"):
        raise TimelineError("UNKNOWN_TRACK", f"Captions follow {timeline.captions.follow}, which has no speech.")


def _track_kind(timeline: Timeline, track_id: str) -> str | None:
    return next((t.kind for t in timeline.tracks if t.id == track_id), None)


def _check_item(timeline: Timeline, track: Track, item: Item) -> None:
    if item.type not in TRACK_ITEMS[track.kind]:
        raise TimelineError("WRONG_TRACK", f"A {item.type} can't go on the {track.kind} track {track.id}.")
    if isinstance(item, ClipItem):
        asset = timeline.assets.get(item.asset)
        if asset is None:
            raise TimelineError("UNKNOWN_ASSET", f"{item.id} uses {item.asset}, which isn't in the project.")
        if track.kind == "audio" and not (asset.kind == "audio" or asset.has_audio):
            raise TimelineError("WRONG_TRACK", f"{asset.id} has no sound to put on the audio track.")
        if track.kind != "audio" and asset.kind == "audio":
            raise TimelineError("WRONG_TRACK", f"{asset.id} is audio only and can't be shown.")
        if item.src_out <= item.src_in or (asset.kind != "image" and item.src_out > asset.frames):
            raise TimelineError("OUT_OF_RANGE", f"{item.id} plays frames {item.src_in}-{item.src_out} of a "
                                                f"{asset.frames}-frame asset.")
    keyframes = getattr(item, "keyframes", {})
    for prop, points in keyframes.items():
        if any(point.f > item.frames for point in points):
            raise TimelineError("OUT_OF_RANGE", f"A {prop} keyframe on {item.id} is past its end.")
