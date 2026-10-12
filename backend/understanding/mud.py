"""The Media Understanding Document (MUD): what the AI editor knows about one asset.

A Clipnera-sized version of BLUEPRINT §2.10: the fields the router, director and
solvers use, nothing more. Times are seconds on the asset's own timeline,
rounded to milliseconds. Built by understanding.build, stored as JSON in S3
next to the asset, and never shown to a model raw: understanding.lcv renders it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.exceptions import CustomException

SCHEMA_VERSION = "1.0.0"

Sec = float
Conf = float
Filler = Literal["um", "uh", "like", "you_know", "i_mean", "so", "repeat"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Word(_Strict):
    i: int
    t0: Sec
    t1: Sec
    text: str
    conf: Conf | None = None
    filler: Filler | None = None


class Utterance(_Strict):
    """A sentence: words ``w0``..``w1`` (inclusive)."""

    id: str
    t0: Sec
    t1: Sec
    w0: int
    w1: int
    text: str


class Silence(_Strict):
    t0: Sec
    t1: Sec
    kind: Literal["pause", "dead_air"]


class Shot(_Strict):
    id: str
    t0: Sec
    t1: Sec
    scene_id: str
    caption: str | None = None
    usable: bool = True
    # blur, dark, bright, fast_motion
    flags: list[str] = Field(default_factory=list)
    blur: float = 0.0
    brightness: float = 0.0
    motion: float = 0.0
    faces: int = 0
    # Horizontal centre of the largest face, 0..1 of the frame width.
    face_x: float | None = None


class Scene(_Strict):
    id: str
    t0: Sec
    t1: Sec
    shot_ids: list[str] = Field(default_factory=list)
    # The first words spoken in it, to recognise it by.
    title: str | None = None


class Beat(_Strict):
    t: Sec
    is_downbeat: bool
    bar: int
    beat_in_bar: int
    conf: Conf = 1.0


class Drop(_Strict):
    t: Sec
    strength: Conf


class Music(_Strict):
    tempo_bpm: float
    drops: list[Drop] = Field(default_factory=list)


class QualityFlag(_Strict):
    flag: str
    t0: Sec
    t1: Sec


class Moment(_Strict):
    id: str
    t0: Sec
    t1: Sec
    score: Conf
    kind: Literal["quote", "action_peak"]
    # A short machine-built reason, e.g. "question + emotion words".
    why: str
    shot_ids: list[str] = Field(default_factory=list)


class MUD(_Strict):
    schema_version: str = SCHEMA_VERSION
    asset_id: str
    kind: Literal["video", "image", "audio"]
    duration: Sec
    width: int | None = None
    height: int | None = None
    has_audio: bool = False
    language: str | None = None
    # analyzer -> "ok" | "skipped" | "failed"
    analyzers: dict[str, str] = Field(default_factory=dict)
    speech_ratio: Conf = 0.0
    words: list[Word] = Field(default_factory=list)
    utterances: list[Utterance] = Field(default_factory=list)
    silences: list[Silence] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    beats: list[Beat] = Field(default_factory=list)
    music: Music | None = None
    quality: list[QualityFlag] = Field(default_factory=list)
    moments: list[Moment] = Field(default_factory=list)


class MudInvalid(CustomException):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="MUD_INVALID", status_code=500)


TOLERANCE = 0.002


def check_mud(mud: MUD) -> None:
    """Raise MudInvalid on the first invariant the document breaks (BLUEPRINT §2.10)."""
    end = mud.duration + TOLERANCE

    def in_range(name: str, t0: float, t1: float) -> None:
        if not (-TOLERANCE <= t0 <= t1 <= end):
            raise MudInvalid(f"{name} {t0}-{t1} is outside 0-{mud.duration}.")

    for word in mud.words:
        in_range(f"word {word.i}", word.t0, word.t1)
    for a, b in zip(mud.words, mud.words[1:]):
        if b.i != a.i + 1 or b.t0 < a.t1 - TOLERANCE:
            raise MudInvalid(f"Words {a.i} and {b.i} are out of order or overlap.")
    for row in (*mud.utterances, *mud.silences, *mud.scenes, *mud.moments, *mud.quality):
        in_range(type(row).__name__.lower(), row.t0, row.t1)
    ids = [row.id for row in (*mud.shots, *mud.scenes, *mud.moments, *mud.utterances)]
    if len(ids) != len(set(ids)):
        raise MudInvalid("Two things share an id.")
    scenes = {scene.id for scene in mud.scenes}
    for shot in mud.shots:
        in_range(f"shot {shot.id}", shot.t0, shot.t1)
        if shot.scene_id not in scenes:
            raise MudInvalid(f"Shot {shot.id} is in scene {shot.scene_id}, which doesn't exist.")
    if mud.kind == "video" and mud.shots:
        # Shots tile the video: from 0, each starting where the last ended, to the end.
        edges = [(s.t0, s.t1) for s in mud.shots]
        if abs(edges[0][0]) > TOLERANCE or abs(edges[-1][1] - mud.duration) > TOLERANCE or any(
            abs(b[0] - a[1]) > TOLERANCE for a, b in zip(edges, edges[1:])
        ):
            raise MudInvalid("Shots don't cover the video from start to end without gaps.")
    for a, b in zip(mud.beats, mud.beats[1:]):
        if b.t <= a.t:
            raise MudInvalid(f"Beats at {a.t} and {b.t} are not increasing.")
    for beat in mud.beats:
        in_range("beat", beat.t, beat.t)
