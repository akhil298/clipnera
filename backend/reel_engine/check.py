"""The accuracy check: before a reel is drawn, a vision model looks at every picture it will show - photos, B-roll,
3D scenes, objects, photo cards - beside the words said at that moment, and the ones that do not show them go.

A wrong picture is worse than none: a galaxy once stood in for "hand on chest" because a stored photo shared one
word with the request. The check only drops what clearly does not fit; a fitting illustration stays.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from core.logging_config import get_logger
from reel_engine.compile import to_output
from reel_engine.media import frame, jpeg
from reel_engine.plan import EditPlan

log = get_logger(__name__)

SYSTEM = """You check a short video edit for wrong pictures. Each item is one picture shown while the speaker says the
quoted words, and what it was meant to show. Answer shows=false only when the picture clearly does not show what is
said or meant (a galaxy for "hand on chest", an empty or broken scene, an unrelated object or place); a fitting
illustration (a heart for heart disease, coins for money, a clock for time) is shows=true. JSON only."""


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Verdict(_M):
    item: int
    shows: bool
    why: str


class Verdicts(_M):
    verdicts: list[Verdict]


def said(plan: EditPlan, start: float, end: float) -> str:
    """The words heard between ``start`` and ``end`` output seconds."""
    heard = []
    for w in plan.audio.words:
        t = to_output(plan.video, w.src, w.t0)
        if t is not None and start - 0.3 <= t <= end + 0.3:
            heard.append(w.text)
    return " ".join(heard)


def picture(path: str, seconds: float) -> bytes:
    """A frame of the asset mid-way (a still for photos and icons); nothing for an animated emoji (Lottie JSON)."""
    if not path or Path(path).suffix.lower() == ".json" or not Path(path).exists():
        return b""
    image = frame(path, seconds / 2 if Path(path).suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"} else 0.0, 360)
    return jpeg(image) if image is not None else b""


async def check(plan: EditPlan) -> int:
    """Drop the pictures that do not show what is said; returns the model calls it took."""
    from reel_engine.ai import vision_json

    items = [(i, i.query or i.label) for i in plan.inserts if i.kind != "footage"]
    items += [(g, g.why or str(g.data.get("text", ""))) for g in plan.graphics if g.kind in ("object", "photocard") and g.asset]
    shown, lines, jpegs = [], [], []
    for item, meant in items:
        image = picture(item.asset.path, item.end - item.start)
        if not image:
            continue
        lines.append(f"item {len(shown)}: meant to show: {meant[:90]}; said meanwhile: \"{said(plan, item.start, item.end)[:160]}\"")
        jpegs.append(image)
        shown.append(item)
    if not shown:
        return 0
    try:
        answer = await vision_json(SYSTEM, "\n".join(lines) + "\n\nOne verdict per item, images in item order. JSON only.", jpegs,
                                   Verdicts, max_tokens=2500, step="reel_check")
    except Exception as exc:  # without the check the reel keeps its pictures, as before it existed
        log.warning("Accuracy check failed, pictures kept: %s", exc)
        return 0
    wrong = {id(shown[v.item]) for v in answer.verdicts if not v.shows and 0 <= v.item < len(shown)}
    if wrong:
        log.info("Accuracy check dropped %d of %d pictures: %s", len(wrong), len(shown),
                 "; ".join(v.why[:60] for v in answer.verdicts if not v.shows))
    plan.inserts = [i for i in plan.inserts if id(i) not in wrong]
    plan.graphics = [g for g in plan.graphics if id(g) not in wrong]
    return 1
