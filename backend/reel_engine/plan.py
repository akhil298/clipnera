"""The Edit Plan: the one document every agent of the reel engine reads and writes.

A plan starts with the sources, gains what the understanding agents found (audio, words, shots),
then the brief, then five tracks (video, graphics, captions, audio) and the assets they use, and
finally the review. The renderer reads only this document; the reels UI shows it; a revision pass
points at any item by its id. Times on the tracks are output seconds; ``src``/``t0``/``t1`` on a
video item are source seconds.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PLAN_VERSION = 1

AudioKind = Literal["voice", "song", "voice_song", "silent"]
Path_ = Literal["voice", "visual"]
CaptionMode = Literal["every_word", "keyword", "none"]
MusicMode = Literal["bed", "score", "none"]
Zoom = Literal["in", "out", "punch", "hold"]
Role = Literal["hook", "montage", "step", "body", "payoff", "cta"]
Sound = Literal["none", "sizzle", "chop", "sparkle", "whoosh", "pop", "pour"]
LAYERS = ("selection", "hook", "story", "picture", "rhythm", "captions", "graphics", "depth", "sound", "finish")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(_Model):
    index: int
    name: str
    path: str
    kind: Literal["video", "image", "audio"]
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 30.0
    has_audio: bool = False


class Word(_Model):
    i: int
    src: int
    t0: float
    t1: float
    text: str
    filler: bool = False


class AudioReport(_Model):
    kind: AudioKind = "silent"
    voice_db: float = -90.0
    music_db: float = -90.0
    lyrics: bool = False
    language: str = ""
    words: list[Word] = Field(default_factory=list)
    voice_paths: dict[int, str] = Field(default_factory=dict)
    why: str = ""


class Box(_Model):
    x: float
    y: float
    w: float
    h: float


class Shot(_Model):
    id: str
    src: int
    t0: float
    t1: float
    faces: list[Box] = Field(default_factory=list)
    motion: float = 0.0
    sharp: bool = True
    dark: bool = False
    what: str = ""


class Section(_Model):
    """A chapter of the story: a recipe step, a point of an argument."""

    lead: str
    text: str
    short: str
    icon: str = ""


class Brief(_Model):
    path: Path_
    audio_kind: AudioKind
    recipe: str
    target_seconds: float
    title_lead: str = ""
    title_text: str = ""
    hook_word: str = ""
    # The on-screen hook over a talking reel's first seconds: a specific question or claim, 3-7 words.
    hook_text: str = ""
    caption_mode: CaptionMode = "every_word"
    # The footage carries its own text (subtitles, cards) and is wider than the reel: each shot is shown whole over
    # a blurred copy of itself, since a 9:16 crop would slice that text.
    fit: bool = False
    # The reel's type kit (data/type_kits.json). text_style/title_style are the looks before kits, kept so older saved
    # plans still load.
    type_kit: str = ""
    text_style: str = ""
    title_style: str = ""
    music: MusicMode = "bed"
    mood: str = "upbeat"
    accent: str = "#ffb020"
    sections: list[Section] = Field(default_factory=list)
    cta: str = ""
    notes: str = ""
    # The editing style the reel is cut by (data/styles.json) and the caption looks it rotates.
    style: str = ""
    caption_looks: list[str] = Field(default_factory=list)


class AssetRef(_Model):
    id: str
    kind: str
    path: str
    licence: str
    source: str
    made: bool = False


class VideoItem(_Model):
    id: str
    src: int
    t0: float
    t1: float
    speed: float = 1.0
    out0: float = 0.0
    out1: float = 0.0
    zoom: Zoom = "hold"
    role: Role = "body"
    section: int = -1
    sound: Sound = "none"
    money: bool = False
    what: str = ""
    keeps_voice: bool = False


class GraphicItem(_Model):
    id: str
    kind: str
    start: float
    end: float
    box: list[int] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    asset: AssetRef | None = None
    place: str = "beside"
    behind: bool = False
    shot: str = ""
    verified: bool = False
    why: str = ""
    by: str = "graphics"


class CaptionLine(_Model):
    id: str
    start: float
    end: float
    lead: str
    keyword: str
    # The line's words in spoken order, each with its second within the line and whether it is the keyword.
    words: list[dict] = Field(default_factory=list)
    icon_query: str = ""
    icon: AssetRef | None = None
    payoff: bool = False
    box: list[int] = Field(default_factory=list)


class AudioItem(_Model):
    id: str
    kind: Literal["voice", "music", "sfx"]
    start: float
    end: float
    asset: AssetRef
    gain: float = 1.0
    src_t0: float = 0.0


class InsertItem(_Model):
    """A related picture cut to while the voice carries on: B-roll, a photo, or the user's own footage."""

    id: str
    kind: Literal["broll", "photo", "footage"]
    start: float
    end: float
    asset: AssetRef
    label: str = ""
    query: str = ""
    src_t0: float = 0.0
    # full = cut away to it; card = a framed photo beside the speaker; object = an animated 3D object or emoji
    # popping in beside the speaker (the kit's, when no photo shows the thing).
    style: Literal["full", "card", "object"] = "full"


class LayerScore(_Model):
    layer: str
    score: int
    note: str = ""


class Review(_Model):
    scores: list[LayerScore] = Field(default_factory=list)
    overall: float = 0.0
    fixes: list[str] = Field(default_factory=list)
    passes: int = 0


class MusicChoice(_Model):
    key: str
    path: str
    title: str
    mood: str
    bpm: float
    offset: float
    licence: str
    source: str


class Progress(_Model):
    stage: str
    note: str = ""
    at: float = 0.0


class EditPlan(_Model):
    version: int = PLAN_VERSION
    sources: list[Source] = Field(default_factory=list)
    audio: AudioReport = Field(default_factory=AudioReport)
    shots: list[Shot] = Field(default_factory=list)
    # Per source: [t, face centre x, face centre y, face width] each sampled second (normalised).
    # Per source: every face seen [t, cx, cy, w, h, mouth motion] (older plans: [t, cx, cy, w]) and, twice a second,
    # the centre of what matters when nobody is on screen [t, cx] (reel_engine/track.py).
    face_track: dict[str, list[list[float]]] = Field(default_factory=dict)
    focus_track: dict[str, list[list[float]]] = Field(default_factory=dict)
    brief: Brief | None = None
    hooks: list[str] = Field(default_factory=list)
    video: list[VideoItem] = Field(default_factory=list)
    graphics: list[GraphicItem] = Field(default_factory=list)
    captions: list[CaptionLine] = Field(default_factory=list)
    inserts: list[InsertItem] = Field(default_factory=list)
    audio_items: list[AudioItem] = Field(default_factory=list)
    music: MusicChoice | None = None
    assets_made: list[AssetRef] = Field(default_factory=list)
    review: Review = Field(default_factory=Review)
    progress: list[Progress] = Field(default_factory=list)
    duration: float = 0.0
    output: str = ""
    ai_calls: int = 0

    def find(self, item_id: str) -> GraphicItem | CaptionLine | VideoItem | None:
        for item in (*self.graphics, *self.captions, *self.video):
            if item.id == item_id:
                return item
        return None
