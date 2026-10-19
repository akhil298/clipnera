"""Clipnera's own assets as one shelf, for the studio's tabs and for the AI to pick from.

Graphics are the animated ones under static/motion/hook_graphics, drawn in code
(hook_transitions.graphics). Sounds are the curated set and the synthesised pack under static/motion/sfx: every one is
cleared for commercial use, and both lists say what each sound is for. The AI names a sound
by id; nothing here is ever invented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

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
