"""Clipnera's own assets as one shelf, for the studio's tabs and for the AI to pick from.

Graphics are the animated ones under static/motion/hook_graphics, drawn in code
(hook_transitions.graphics). B-roll is the public-domain shelf broll.collect fills (BROLL_LIBRARY_DIR),
landscape originals each with its licence row in CREDITS.csv; public-domain shots only. Music is the
beds composed in code under static/motion/music (scripts/build_synth_music.py), Clipnera's own. Sounds are the curated set and the synthesised pack under static/motion/sfx: every one is
cleared for commercial use, and both lists say what each sound is for. The AI names a sound
by id; nothing here is ever invented.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from brain.schema import BrollAdded, MusicAdded
from core.config import get_settings
from core.exceptions import CustomException
from edit_engine.perception import probe_media
from hook_transitions import graphics as shelf_graphics

SFX_DIR = Path(__file__).resolve().parent.parent / "static" / "motion" / "sfx"
SFX_URL = "/static/sfx"
CURATED_LICENCE = "Clipnera library (cleared for commercial use)"
# What each curated sound is for; the synthesised pack carries its own tags.
CURATED_TAGS = {
    "pop": ["pop", "bubble", "ui", "text"], "click": ["click", "ui", "button"], "soft_click": ["click", "soft", "ui"],
    "whoosh": ["whoosh", "transition", "swoosh", "cut"], "whoosh_short": ["whoosh", "fast", "transition", "cut"],
    "ding": ["ding", "bell", "notification", "number"], "cash": ["cash", "money", "register"],
    "tick": ["tick", "clock", "ui"], "boom": ["boom", "impact", "hit", "reveal"], "riser": ["riser", "build", "tension"],
}


@dataclass(frozen=True)
class Sound:
    id: str
    file: str
    seconds: float
    # Where its loudest moment is, in seconds: that point is lined up with the event it marks.
    peak: float
    category: str
    tags: tuple[str, ...]
    licence: str

    @property
    def url(self) -> str:
        return f"{SFX_URL}/{self.file}"

    @property
    def name(self) -> str:
        return self.id.replace("_", " ").replace(" 0p", " 0.").title()


def _read(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text()) if path.exists() else {}


@lru_cache(maxsize=1)
def sounds() -> dict[str, Sound]:
    """Every sound on the shelf, by id: the curated ones first."""
    shelf: dict[str, Sound] = {}
    for sound_id, entry in _read(SFX_DIR / "manifest.json").items():
        tags = CURATED_TAGS.get(sound_id, [sound_id])
        shelf[sound_id] = Sound(sound_id, entry["file"], float(entry.get("seconds", 0)), float(entry.get("peak", 0)),
                                tags[0], tuple(tags), CURATED_LICENCE)
    for sound_id, entry in _read(SFX_DIR / "synth" / "manifest.json").items():
        shelf.setdefault(sound_id, Sound(
            sound_id, f"synth/{entry['file']}", float(entry.get("seconds", 0)), float(entry.get("peak", 0)),
            str(entry.get("category") or "other"), tuple(entry.get("tags") or [sound_id]),
            str(entry.get("licence") or CURATED_LICENCE)))
    return shelf


def search_sounds(query: str = "", category: str = "") -> list[Sound]:
    """Sounds whose name, category or tags hold every word of ``query``."""
    words = [word for word in query.lower().replace("_", " ").split() if word]
    found = []
    for sound in sounds().values():
        if category and sound.category != category:
            continue
        haystack = " ".join([sound.id.replace("_", " "), sound.category, *sound.tags])
        if all(word in haystack for word in words):
            found.append(sound)
    return found


GRAPHICS_URL = "/static/graphics"


def graphics() -> dict[str, shelf_graphics.Graphic]:
    """Every animated graphic on the shelf, by id."""
    return shelf_graphics.library()


BROLL_URL = "/static/broll"
# The owner's rule: B-roll is public domain only (no attribution licences).
BROLL_LICENCES = frozenset({"pd_us_gov", "public_domain", "cc0"})


@dataclass(frozen=True)
class BrollShot:
    # The shot's path under the library, e.g. "food/coffee/pour-shot2/pour-shot2.mp4".
    id: str
    title: str
    category: str
    topic: str
    seconds: float
    licence: str
    credit: str

    @property
    def url(self) -> str:
        return f"{BROLL_URL}/{self.id}"


def broll_dir() -> Path:
    configured = get_settings().BROLL_LIBRARY_DIR
    return Path(configured) if configured else Path(__file__).resolve().parent.parent.parent / "broll_library"


@lru_cache(maxsize=1)
def broll() -> dict[str, BrollShot]:
    """Every public-domain shot on the B-roll shelf that is present, by id."""
    root = broll_dir()
    credits = root / "CREDITS.csv"
    if not credits.exists():
        return {}
    with credits.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("commercial_ok") == "True" and r.get("license_code") in BROLL_LICENCES
                and (root / r["file"]).exists()]
    return {r["file"]: BrollShot(r["file"], r["title"], r["category"], r["topic"], float(r["shot_seconds"] or 0),
                                 r["license_code"], r["attribution_text"]) for r in rows}


def search_broll(query: str = "", limit: int = 40) -> list[BrollShot]:
    """Shots matching every word of ``query``: matches in the shot's own title first (its topic is only
    the search that collected it, so it can be loose)."""
    words = [w for w in query.lower().split() if w]
    found = [shot for shot in broll().values()
             if all(w in f"{shot.title} {shot.topic} {shot.category}".lower() for w in words)]
    found.sort(key=lambda shot: (-sum(w in shot.title.lower() for w in words), -sum(w in shot.topic.lower() for w in words)))
    return found[:limit]


async def broll_added(service: Any, user_id: str, project_id: str, shot_id: str) -> BrollAdded:
    """A shelf shot copied into the project, with what ``add_asset`` needs to know about it."""
    shot = broll().get(shot_id)
    if shot is None:
        raise CustomException(message="That B-roll shot isn't on the shelf.", code="NOT_FOUND", status_code=404)
    path = broll_dir() / shot.id
    info = await probe_media(str(path))
    key = await service.import_file(user_id, project_id, path, "video/mp4")
    return BrollAdded(key=key, seconds=round(info.duration, 3), width=info.width, height=info.height)


MUSIC_DIR = Path(__file__).resolve().parent.parent / "static" / "motion" / "music"
MUSIC_URL = "/static/music"


@dataclass(frozen=True)
class MusicTrack:
    id: str
    name: str
    mood: str
    tags: tuple[str, ...]
    bpm: float
    seconds: float
    file: str
    licence: str

    @property
    def url(self) -> str:
        return f"{MUSIC_URL}/{self.file}"


@lru_cache(maxsize=1)
def music() -> dict[str, MusicTrack]:
    """Every music bed on the shelf, by id."""
    return {track_id: MusicTrack(track_id, e["name"], e["mood"], tuple(e["tags"]), float(e["bpm"]), float(e["seconds"]),
                                 e["file"], e["licence"])
            for track_id, e in _read(MUSIC_DIR / "manifest.json").items() if (MUSIC_DIR / e["file"]).exists()}


def search_music(query: str = "") -> list[MusicTrack]:
    """Tracks whose name, mood or tags hold every word of ``query``."""
    words = query.lower().split()
    return [t for t in music().values() if all(w in f"{t.name} {t.mood} {' '.join(t.tags)}".lower() for w in words)]


async def music_added(service: Any, user_id: str, project_id: str, track_id: str) -> MusicAdded:
    """A music bed copied into the project, for an ``add_asset`` (kind audio) and the music track."""
    track = music().get(track_id)
    if track is None:
        raise CustomException(message="That music isn't on the shelf.", code="NOT_FOUND", status_code=404)
    key = await service.import_file(user_id, project_id, MUSIC_DIR / track.file, "audio/mp4")
    return MusicAdded(key=key, seconds=track.seconds)
