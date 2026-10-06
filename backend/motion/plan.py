"""The motion plan stored on a clip: graphic cues in source seconds."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

PLAN_VERSION = 1

# Graphic templates (see motion.graphics).
LIST_CARD = "list_card"
BIG_NUMBER = "big_number"
ENTITY_TAG = "entity_tag"
CTA_CARD = "cta_card"
REACTION = "reaction_sticker"
KINDS = (LIST_CARD, BIG_NUMBER, ENTITY_TAG, CTA_CARD, REACTION)
# Cards big enough that the captions step aside while they are up; the card
# already shows what is being said.
QUIETS_CAPTIONS = frozenset({LIST_CARD, BIG_NUMBER, CTA_CARD})


@dataclass
class Cue:
    """One graphic on screen from ``start`` to ``end`` (source seconds).

    ``beats`` are source seconds where parts of it appear (a list's items),
    ``data`` the template's fields, every text in it taken from the speech.
    """

    kind: str
    start: float
    end: float
    data: dict[str, Any] = field(default_factory=dict)
    beats: list[float] = field(default_factory=list)
    why: str = ""


@dataclass
class MotionPlan:
    mood: str = "neutral"
    cues: list[Cue] = field(default_factory=list)
    version: int = PLAN_VERSION


def dump_plan(plan: MotionPlan) -> dict[str, Any]:
    return asdict(plan)


def load_plan(value: Any) -> MotionPlan | None:
    """A stored plan (dict or JSON text); ``None`` when absent or unreadable."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, dict):
        return None
    try:
        cues = [Cue(**cue) for cue in value.get("cues") or [] if isinstance(cue, dict) and cue.get("kind") in KINDS]
    except TypeError:
        return None
    return MotionPlan(mood=str(value.get("mood") or "neutral"), cues=cues, version=int(value.get("version") or 0))
