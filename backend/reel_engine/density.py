"""Density: something new on screen every few seconds, the way the best human edits run (5-12 graphics in 20 s).

Once the director's graphics, the photos and the scenes are placed, any stretch of plain talking head longer than
``GAP`` seconds gets a 3D object or an animated emoji for a big word said in it (a caption's keyword), popping in
beside the speaker. The icon check only accepts an icon that literally shows the word; a stretch with no showable
word stays as it is.
"""

from __future__ import annotations

from core.logging_config import get_logger
from reel_engine.plan import CaptionLine, EditPlan, GraphicItem

log = get_logger(__name__)

GAP = 3.5      # seconds of plain talking head that get something new on screen
HOLD = 1.8     # how long a filled-in object stays
SPACING = 1.2  # seconds of plain picture kept between two filled-in objects
# Graphics that run along the reel or close it: they are not something new on screen.
QUIET = {"progress", "accent", "cta"}


def gaps(plan: EditPlan) -> list[tuple[float, float]]:
    """Stretches with no story graphic, object, photo or scene on screen, in order."""
    busy = sorted([(g.start, g.end) for g in plan.graphics if g.kind not in QUIET] + [(i.start, i.end) for i in plan.inserts])
    out, t, end = [], 0.0, plan.duration - 0.5
    for a, b in busy:
        if a - t >= GAP:
            out.append((t, a))
        t = max(t, b)
    if end - t >= GAP:
        out.append((t, end))
    return out


def keyword_at(line: CaptionLine) -> float:
    return line.start + next((w.get("at", 0.0) for w in line.words if w.get("key")), 0.0)


def spots(plan: EditPlan) -> list[tuple[float, CaptionLine]]:
    """In each gap, the caption keywords to show, one about every ``HOLD + SPACING`` seconds, each at its word."""
    lines = sorted((c for c in plan.captions if c.keyword.strip()), key=keyword_at)
    out: list[tuple[float, CaptionLine]] = []
    for a, b in gaps(plan):
        t = a + 0.6
        while t + HOLD <= b - 0.2:
            line = next((c for c in lines if t <= keyword_at(c) <= t + 1.5 and keyword_at(c) + HOLD <= b - 0.2), None)
            if line is None:
                t += 0.8
                continue
            at = keyword_at(line)
            out.append((at, line))
            t = at + HOLD + SPACING
    return out


async def fill(plan: EditPlan) -> int:
    """Fill the reel's plain stretches; returns the model calls it took."""
    from reel_engine import icons

    picks = spots(plan)
    if not picks:
        return 0
    found = await icons.choose([(line.keyword, " ".join(w["text"] for w in line.words)) for _, line in picks],
                               animated=frozenset(range(len(picks))), kinds=("object3d",), n=16)
    added = 0
    for (at, line), asset in zip(picks, found):
        if asset is None:
            continue
        plan.graphics.append(GraphicItem(id=f"f{added}", kind="object", start=round(at, 3), end=round(min(at + HOLD, plan.duration - 0.2), 3),
                                         asset=asset, data={"text": ""}, place="beside", why=f"shows '{line.keyword}' as it is said",
                                         by="density"))
        added += 1
    plan.graphics.sort(key=lambda g: g.start)
    log.info("Density: %d objects added for %d words asked", added, len(picks))
    return 1


def one_of_each(plan: EditPlan) -> int:
    """No icon twice in a reel: the same cartoon car three times reads as a template. A repeated pop-in object goes,
    a repeated icon on a label or caption line is left off (its words stay). Returns how many repeats were removed."""
    seen: set[str] = set()
    removed = 0
    keep = []
    for g in sorted(plan.graphics, key=lambda g: g.start):
        if g.asset is not None and g.asset.kind == "icon":
            if g.asset.id in seen:
                removed += 1
                if g.kind == "object":
                    continue
                g.asset = None
            else:
                seen.add(g.asset.id)
        keep.append(g)
    plan.graphics = keep
    for c in sorted(plan.captions, key=lambda c: c.start):
        if c.icon is not None:
            if c.icon.id in seen:
                c.icon = None
                removed += 1
            else:
                seen.add(c.icon.id)
    return removed

