"""The graphic beats stored on a Pro clip: one graphic per spoken idea, in source seconds.

A beat is what the Before/After reels do on almost every line (see
``before_after_reels/ANALYSIS.md``): a number counts up, a list builds item by
item as it is said, a brand's logo pops, a key word lands behind the speaker,
a full card states the point. Every text a beat shows is made of the words it
is anchored to; the planner proves that before a beat is kept.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

PLAN_VERSION = 1

COUNT_UP = "count_up"
LIST = "list"
LOGO = "logo"
NAME = "name"
KEYWORD = "keyword"
STATEMENT = "statement"
OBJECT = "object"
CHART = "chart"
FLOW = "flow"
UI = "ui"
IMAGE = "image"
CTA = "cta"
MAP = "map"
KINDS = (COUNT_UP, LIST, LOGO, NAME, KEYWORD, STATEMENT, OBJECT, CHART, FLOW, UI, IMAGE, CTA, MAP)

# Where a beat sits. ``card`` fills the frame; ``behind`` is a full-frame layer
# under the cut-out speaker; ``beside`` is a pop near the head; ``panel`` a box
# in the free part of the frame.
CARD, BEHIND, BESIDE, PANEL = "card", "behind", "beside", "panel"
PLACES = (CARD, BEHIND, BESIDE, PANEL)
# Beats that hold the frame or a big box: the captions step aside while they are up.
QUIETS_CAPTIONS = frozenset({STATEMENT, IMAGE, LIST, FLOW, UI, CHART})

LIST_MARKS = ("none", "check", "cross")
UI_VARIANTS = ("search", "notification", "chat", "checklist")
TRENDS = ("up", "down", "none")


@dataclass
class Beat:
    """One graphic from ``start`` to ``end`` (source seconds).

    ``steps`` are source seconds where parts of it land (a list's items, a
    flow's stages); ``data`` holds the template's fields, ``asset`` a kit path.
    """

    kind: str
    start: float
    end: float
    place: str = BESIDE
    data: dict[str, Any] = field(default_factory=dict)
    steps: list[float] = field(default_factory=list)
    asset: str = ""
    why: str = ""

    @property
    def quiets_captions(self) -> bool:
        return self.place == CARD or self.kind in QUIETS_CAPTIONS


@dataclass
class BeatPlan:
    theme: str = "clean"
    beats: list[Beat] = field(default_factory=list)
    version: int = PLAN_VERSION


def dump_plan(plan: BeatPlan) -> dict[str, Any]:
    return asdict(plan)


def load_plan(value: Any) -> BeatPlan | None:
    """A stored plan (dict or JSON text); ``None`` when absent or unreadable."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, dict):
        return None
    try:
        beats = [Beat(**beat) for beat in value.get("beats") or [] if isinstance(beat, dict) and beat.get("kind") in KINDS]
    except TypeError:
        return None
    return BeatPlan(theme=str(value.get("theme") or "clean"), beats=beats, version=int(value.get("version") or 0))
