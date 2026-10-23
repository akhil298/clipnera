"""Accents: motion graphics from the Lottie library on the moments that call for one, and varied transition sounds.

An accent is never decoration for its own sake: the call to action gets a follow button, the payoff line a short
burst, a number counting up a money or growth animation. Each is placed from the box of the item it serves (so it
runs after layout) and picked by the reel's own seed, so two reels rarely share one. Sounds come from the sound
library by role (whoosh, impact, click), rotated so a reel never repeats the same whoosh.
"""

from __future__ import annotations

import json
import zlib
from functools import lru_cache
from pathlib import Path

from reel_engine.media import H, W
from reel_engine.plan import AssetRef, EditPlan, GraphicItem

MOTION = Path(__file__).resolve().parents[1] / "static" / "motion"
CURRENCY = ("$", "₹", "€", "£", "rs", "rupee", "dollar", "money", "cash", "lakh", "crore", "salary", "income", "profit")
ACCENT_SIZE = 300
BURST_SECONDS = 1.6
# The longest sound a role may use here: a long swell under a one-second card smears.
SOUND_MAX_SECONDS = {"whoosh": 1.6, "transition": 1.6, "impact": 1.8, "click": 0.6, "riser": 4.0}


@lru_cache(maxsize=4)
def _library(folder: str) -> dict:
    path = MOTION / folder / "manifest.json"
    return json.loads(path.read_text()).get("entries", {}) if path.exists() else {}


def seed_of(plan: EditPlan) -> int:
    return zlib.crc32(f"{plan.sources[0].path if plan.sources else ''}{plan.duration}".encode())


def animation(role: str, seed: int) -> AssetRef | None:
    """A Lottie accent for ``role``, roughly square so it sits in a square box, varied by ``seed``."""
    found = sorted((key, e) for key, e in _library("lottie").items() if e["role"] == role
                   and e.get("w") and e.get("h") and 0.6 <= e["w"] / e["h"] <= 1.6 and (MOTION / "lottie" / e["file"]).exists())
    if not found:
        return None
    key, e = found[seed % len(found)]
    return AssetRef(id=key, kind="motion", path=str(MOTION / "lottie" / e["file"]), licence=e["licence"], source=e["source"])


def sound(role: str, n: int, seed: int = 0) -> AssetRef | None:
    """The ``n``th sound of ``role`` for this reel (rotating), or None when the library has none."""
    limit = SOUND_MAX_SECONDS.get(role, 2.0)
    found = sorted((key, e) for key, e in _library("sfx/library").items()
                   if e["role"] == role and 0 < e["seconds"] <= limit and (MOTION / "sfx" / "library" / e["file"]).exists())
    if not found:
        return None
    key, e = found[(seed + n * 7) % len(found)]
    return AssetRef(id=f"sfx.{key}", kind="sfx", path=str(MOTION / "sfx" / "library" / e["file"]), licence=e["licence"], source=e["source"])


def _around(box: list[int], size: int, above: bool) -> list[int]:
    x, y, w, h = box
    left = max(0, min(W - size, x + w // 2 - size // 2))
    top = max(0, y - size + 20) if above else max(0, min(H - size, y + h // 2 - size // 2))
    return [left, top, size, size]


def add(plan: EditPlan) -> int:
    """Accents for the call to action, the payoff line and numbers counting up; returns how many were added."""
    seed = seed_of(plan)
    wanted: list[tuple[str, float, float, list[int]]] = []
    for g in plan.graphics:
        if not g.box:
            continue
        if g.kind == "cta":
            wanted.append(("follow", g.start + 0.15, g.end, _around(g.box, ACCENT_SIZE, above=True)))
        elif g.kind == "count_up":
            said = f"{g.data.get('prefix', '')} {g.data.get('suffix', '')} {g.data.get('label', '')}".lower()
            role = "money" if any(c in said for c in CURRENCY) else "growth"
            wanted.append((role, g.start + 0.2, g.end, _around(g.box, ACCENT_SIZE, above=True)))
    payoff = next((c for c in plan.captions if c.payoff and c.box), None)
    if payoff:
        wanted.append(("burst", payoff.start, min(payoff.end, payoff.start + BURST_SECONDS), _around(payoff.box, ACCENT_SIZE * 2, above=False)))
    added = 0
    for n, (role, start, end, box) in enumerate(wanted):
        asset = animation(role, seed + n)
        if asset and end - start >= 0.5:
            plan.graphics.append(GraphicItem(id=f"a{n}", kind="accent", start=round(start, 3), end=round(end, 3), box=box, asset=asset,
                                             data={"role": role}, place="beside", why=f"{role} accent", by="accents"))
            added += 1
    plan.graphics.sort(key=lambda g: g.start)
    return added
