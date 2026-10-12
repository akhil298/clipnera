"""IntentFrame: what the user asked for, with every explicit ask as a predicate code can check
on the finished Timeline (BLUEPRINT §3B.1.3, §3B.4.2).

"30 seconds", "9:16", "title 'Goa 2026'", "flash on every drop" are not hopes: each becomes a
PredicateSpec, and a plan that doesn't make every one true scores zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from brain.plan_ir import Aspect, StepKind
from editor.timeline import ClipItem, GraphicItem, MusicItem, TextItem, Timeline
from understanding.mud import MUD

PredicateKind = Literal["durationBetween", "aspectIs", "textPresent", "solidOnEvents", "musicPresent",
                        "captionsPresent", "rangeRemoved", "rangeKept", "and", "or"]
ASPECTS: dict[str, float] = {"9:16": 9 / 16, "1:1": 1.0, "4:5": 4 / 5, "16:9": 16 / 9}
# A flash must start within this many frames of its event.
EVENT_TOLERANCE_FRAMES = 1


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PredicateSpec(_Closed):
    kind: PredicateKind
    # durationBetween: min_s, max_s · aspectIs: aspect · textPresent: text · solidOnEvents: events
    # ("drops"|"downbeats"), asset? · rangeRemoved/rangeKept: asset, t0, t1 (seconds of the source).
    args: dict[str, Any] = Field(default_factory=dict)
    children: list[PredicateSpec] = Field(default_factory=list)


class Ask(_Closed):
    id: str
    kind: StepKind
    text: str = Field(..., max_length=200)
    predicate: PredicateSpec | None = None


class Interpretation(_Closed):
    summary: str = Field(..., max_length=200)
    p: float = Field(..., ge=0, le=1)
    # How different the result would be from the most likely reading, 0 (same) to 1 (nothing alike).
    distance: float = Field(0.0, ge=0, le=1)
    # The chip that picks this reading, if asked.
    option: str = Field("", max_length=40)


class IntentFrame(_Closed):
    asks: list[Ask] = Field(default_factory=list)
    implied: list[str] = Field(default_factory=list)
    platform: Literal["reels", "tiktok", "shorts", "youtube", "ad", "podcast_clip", "wedding", "travel",
                      "tutorial", "generic"] = "generic"
    genre: str = "generic"
    mood: list[str] = Field(default_factory=list)
    target_seconds: float | None = None
    aspect: Aspect | None = None
    scope: Literal["whole", "selection", "items", "range"] = "whole"
    confidence: float = Field(1.0, ge=0, le=1)
    interpretations: list[Interpretation] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, max_length=5)


def check(spec: PredicateSpec, timeline: Timeline, muds: Mapping[str, MUD]) -> bool:
    """Whether ``timeline`` makes ``spec`` true."""
    return _CHECKERS[spec.kind](spec, timeline, muds)


def failed_asks(frame: IntentFrame, timeline: Timeline, muds: Mapping[str, MUD]) -> list[Ask]:
    return [ask for ask in frame.asks if ask.predicate is not None and not check(ask.predicate, timeline, muds)]


def _duration(spec: PredicateSpec, timeline: Timeline, _: Mapping[str, MUD]) -> bool:
    seconds = timeline.duration / timeline.fps
    return float(spec.args.get("min_s", 0)) - 1e-6 <= seconds <= float(spec.args.get("max_s", 1e9)) + 1e-6


def _aspect(spec: PredicateSpec, timeline: Timeline, _: Mapping[str, MUD]) -> bool:
    wanted = ASPECTS.get(str(spec.args.get("aspect")))
    return wanted is not None and abs(timeline.width / timeline.height - wanted) < 0.01


def _text(spec: PredicateSpec, timeline: Timeline, _: Mapping[str, MUD]) -> bool:
    wanted = str(spec.args.get("text", "")).casefold().strip()
    return bool(wanted) and any(
        isinstance(item, TextItem) and wanted in item.text.casefold() for track in timeline.tracks for item in track.items
    )


def is_solid(item: Any) -> bool:
    """A flash frame: a graphic item the compiler made as a solid (brain.compile)."""
    return isinstance(item, GraphicItem) and item.extra.get("solid") is not None


def event_frames(timeline: Timeline, muds: Mapping[str, MUD], events: str, asset: str | None = None) -> list[int]:
    """Timeline frames of the music's drops or downbeats, where the music plays."""
    frames: list[int] = []
    for track in timeline.tracks:
        for item in track.items:
            if not (isinstance(item, ClipItem) and track.kind == "audio") or (asset and item.asset != asset):
                continue
            mud = muds.get(item.asset)
            if mud is None:
                continue
            times = [d.t for d in mud.music.drops] if events == "drops" and mud.music else \
                [b.t for b in mud.beats if b.is_downbeat] if events == "downbeats" else []
            for t in times:
                source = round(t * timeline.fps)
                if item.src_in <= source < item.src_out:
                    frames.append(item.at + round((source - item.src_in) / item.speed))
    return sorted(frames)


def _solid(spec: PredicateSpec, timeline: Timeline, muds: Mapping[str, MUD]) -> bool:
    targets = event_frames(timeline, muds, str(spec.args.get("events", "drops")), spec.args.get("asset"))
    starts = [item.at for track in timeline.tracks for item in track.items if is_solid(item)]
    return bool(targets) and all(any(abs(s - t) <= EVENT_TOLERANCE_FRAMES for s in starts) for t in targets)


def _music(_: PredicateSpec, timeline: Timeline, muds: Mapping[str, MUD]) -> bool:
    for track in timeline.tracks:
        for item in track.items:
            if isinstance(item, MusicItem):
                return True
            if track.kind == "audio" and isinstance(item, ClipItem):
                mud = muds.get(item.asset)
                if mud is None or mud.music is not None or timeline.assets[item.asset].kind == "audio":
                    return True
    return False


def _captions(_: PredicateSpec, timeline: Timeline, __: Mapping[str, MUD]) -> bool:
    return timeline.captions is not None and timeline.captions.enabled


def _covered(spec: PredicateSpec, timeline: Timeline) -> float:
    """Share of the source range [t0, t1] of an asset that some clip plays."""
    asset = spec.args.get("asset")
    lo, hi = round(float(spec.args["t0"]) * timeline.fps), round(float(spec.args["t1"]) * timeline.fps)
    if hi <= lo:
        return 0.0
    played: list[tuple[int, int]] = sorted(
        (max(lo, item.src_in), min(hi, item.src_out))
        for track in timeline.tracks for item in track.items
        if isinstance(item, ClipItem) and item.asset == asset and track.kind != "audio"
    )
    covered, reach = 0, lo
    for start, end in played:
        start = max(start, reach)
        if end > start:
            covered += end - start
            reach = end
    return covered / (hi - lo)


def _removed(spec: PredicateSpec, timeline: Timeline, _: Mapping[str, MUD]) -> bool:
    return _covered(spec, timeline) <= 0.05


def _kept(spec: PredicateSpec, timeline: Timeline, _: Mapping[str, MUD]) -> bool:
    return _covered(spec, timeline) >= 0.9


def _all(spec: PredicateSpec, timeline: Timeline, muds: Mapping[str, MUD]) -> bool:
    return all(check(child, timeline, muds) for child in spec.children)


def _any(spec: PredicateSpec, timeline: Timeline, muds: Mapping[str, MUD]) -> bool:
    return any(check(child, timeline, muds) for child in spec.children)


_CHECKERS = {
    "durationBetween": _duration, "aspectIs": _aspect, "textPresent": _text, "solidOnEvents": _solid,
    "musicPresent": _music, "captionsPresent": _captions, "rangeRemoved": _removed, "rangeKept": _kept,
    "and": _all, "or": _any,
}
