"""The motion-graphics library laid over a hook bridge.

``static/motion/hook_graphics`` holds graphics rendered by
``hook_transitions.graphics_source.render``: packed-alpha MP4s (colour left,
matte right) with a matching sound effect each, listed in ``manifest.json``.
Auto picks one per clip at random, leaning towards graphics whose moods match
the hook; the pick is seeded by the clip id, so a batch gets variety while a
re-export of one clip looks the same.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)

LIBRARY_DIR = Path(__file__).resolve().parent.parent / "static" / "motion" / "hook_graphics"
# How much a graphic whose moods match the hook outweighs one that does not.
MOOD_WEIGHT = 3


@dataclass(frozen=True)
class Graphic:
    id: str
    name: str
    video: Path
    sfx: Path | None
    duration: float
    moods: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "description": f"{self.name} motion graphic with its own sound effect"}


@lru_cache(maxsize=1)
def library(root: Path = LIBRARY_DIR) -> dict[str, Graphic]:
    """Graphics whose files are present, by id; empty when the library is missing."""
    path = root / "manifest.json"
    if not path.exists():
        log.warning("Hook graphics library missing at %s; bridges render without graphics", root)
        return {}
    spec = json.loads(path.read_text())
    found: dict[str, Graphic] = {}
    for entry in spec.get("graphics") or []:
        video = root / entry["file"]
        if not video.exists():
            continue
        sfx = root / entry["sfx"] if entry.get("sfx") else None
        found[entry["id"]] = Graphic(
            id=entry["id"], name=entry["name"], video=video,
            sfx=sfx if sfx and sfx.exists() else None,
            duration=float(spec.get("duration") or 1.0), moods=tuple(entry.get("moods") or ()),
        )
    return found


def pick_graphic(clip_id: str, intents: list[str]) -> str | None:
    """A graphic for a clip: random, weighted towards ones matching its intents."""
    graphics = list(library().values())
    if not graphics:
        return None
    pool = [g for g in graphics for _ in range(MOOD_WEIGHT if set(g.moods).intersection(intents) else 1)]
    digest = hashlib.sha1(f"{clip_id}:graphic".encode("utf-8")).digest()
    return pool[int.from_bytes(digest[:4], "big") % len(pool)].id
