"""Review, after the render: a head editor scores the reel on the ten premium layers and says what to fix.

The reviewer sees a frame at every graphic and caption (with what was meant to be shown there), frames from
across the reel, and measurements code can take for certain: loudness, voice level against music, length,
the number of cuts and graphics. It returns a 1-10 score per layer and, for each item, keep / move / drop /
shorten. ``apply`` makes those changes to the plan so the next pass re-lays and re-renders only the graphics.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.logging_config import get_logger
from reel_engine.ai import vision_json
from reel_engine.media import frame, jpeg, loudness, stamp
from reel_engine.plan import LAYERS, EditPlan, LayerScore, Review

log = get_logger(__name__)

MAX_ITEM_FRAMES = 24


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Score(_M):
    layer: Literal["selection", "hook", "story", "picture", "rhythm", "captions", "graphics", "depth", "sound", "finish"]
    score: int
    note: str


class Action(_M):
    id: str
    action: Literal["keep", "move", "drop", "shorten", "enlarge", "shrink"]
    why: str


class Verdict(_M):
    scores: list[Score]
    actions: list[Action]
    fixes: list[str]


SYSTEM = f"""You are the head editor of a premium short-form studio reviewing a finished vertical reel before it
ships, against the best $120 human edits. Score each of the ten layers 1-10 ({', '.join(LAYERS)}): selection
(only strong moments), hook (first 2 s stop the scroll), story (clear shape, right length), picture (framing on
the subject, stable, graded, exposure matched), rhythm (framing changes, pace), captions (readable, accurate,
well placed; 'none' is right when nobody talks - score it 8 then), graphics (fit what is said or shown, taste,
variety, pacing), depth (text behind the person, inserts), sound (judge from the measurements), finish (title,
CTA, clean end).
Score against fixed anchors, the same for every reel: 3 = broken (missing captions, faces cut off, text off screen);
5 = a creator's own quick amateur edit; 7 = a competent freelance editor's work (clean, framed on the subject,
accurate captions, fitting graphics); 8 = a strong agency edit; 9 = among the best reels in its niche; 10 =
flawless. A reel that is clean, correct and well framed with accurate captions is at least 7 on those layers;
reserve 9-10 for work a top editor would sign. Sound: loudness between -16 and -12 LUFS with the voice clearly over
the music is 8 or more. Item frames are stills: one may catch a graphic entering or leaving; judge what it means to
show, not the half-drawn moment.
For every item frame, decide: keep; move (it covers a face, the product or the action, or sits badly); drop
(wrong, redundant or cluttering); shorten (stays too long); enlarge (too small to read on a phone); shrink (too big,
crowds the frame). fixes = at most 5 concrete changes. JSON only."""


def _item_frames(plan: EditPlan, video: str) -> tuple[list[bytes], list[str]]:
    items = [(g.id, f"effect {g.data['effect']}" if g.kind == "effect" else g.kind, g.start, g.end,
              " / ".join(g.data.get("texts") or []) if g.kind == "effect" else g.data.get("text") or g.data.get("label") or g.data.get("lead") or "")
             for g in plan.graphics if g.kind not in ("wash", "progress") and not (g.kind == "effect" and g.data.get("part") == "back")]
    items += [(c.id, "caption", c.start, c.end, f"{c.lead} {c.keyword}") for c in plan.captions]
    items.sort(key=lambda i: i[2])
    if len(items) > MAX_ITEM_FRAMES:
        step = len(items) / MAX_ITEM_FRAMES
        items = [items[int(k * step)] for k in range(MAX_ITEM_FRAMES)]
    jpegs, notes = [], []
    for item_id, kind, start, end, text in items:
        image = frame(video, start + min(0.8, (end - start) * 0.6), 432)
        if image is None:
            continue
        jpegs.append(jpeg(stamp(image, f"{item_id} {start:.1f}s")))
        notes.append(f"{item_id} {kind} at {start:.1f}s: {str(text)[:60]}")
    return jpegs, notes


def _overview(plan: EditPlan, video: str, count: int = 6) -> list[bytes]:
    out = []
    for k in range(count):
        t = plan.duration * (k + 0.5) / count
        image = frame(video, t, 360)
        if image is not None:
            out.append(jpeg(stamp(image, f"{t:.1f}s")))
    return out


async def review(plan: EditPlan, video: str) -> tuple[Review, list[Action]]:
    item_jpegs, notes = _item_frames(plan, video)
    overview = _overview(plan, video)
    lufs = loudness(video)
    talking = sum(i.out1 - i.out0 for i in plan.video if i.keeps_voice)
    facts = (f"Length {plan.duration:.1f} s, {len(plan.video)} shots, {len(plan.graphics)} graphics, {len(plan.captions)} caption lines. "
             f"Audio: {plan.audio.kind}; voice in {talking / max(plan.duration, 0.1):.0%} of the reel; music "
             f"{plan.brief.music if plan.brief else 'none'}; integrated loudness {lufs:.1f} LUFS (target -14); "
             f"{sum(1 for a in plan.audio_items if a.kind == 'sfx')} sound effects. Recipe: {plan.brief.recipe if plan.brief else ''}."
             + (f" Spoken language: {plan.audio.language}; captions are that speech written in Roman letters (Hinglish/Tenglish "
                "style), so judge them as that language, not as English." if plan.audio.language not in ("", "en", "english") else ""))
    message_text = (f"Measurements: {facts}\n\nFirst {len(overview)} images: frames across the reel. Then one image per item:\n"
                    + "\n".join(notes) + "\n\nReview it. JSON only.")
    verdict = await vision_json(SYSTEM, message_text, overview + item_jpegs, Verdict, max_tokens=4000)
    scores = [LayerScore(layer=s.layer, score=max(1, min(10, s.score)), note=s.note) for s in verdict.scores]
    overall = round(sum(s.score for s in scores) / len(scores), 1) if scores else 0.0
    log.info("Review: overall %.1f", overall)
    return Review(scores=scores, overall=overall, fixes=verdict.fixes[:5]), verdict.actions


# The reel's structure: a revision may move or shorten these, never delete them.
STRUCTURE = {"chapter", "progress", "wash", "flicker", "cta"}


def apply(plan: EditPlan, actions: list[Action]) -> int:
    """Make the reviewer's item changes; returns how many items changed."""
    changed = 0
    structural = {g.id for g in plan.graphics if g.kind in STRUCTURE or g.why == "hook word" or g.by == "finish"
                  or (g.kind == "effect" and g.data.get("layer") == "picture")}
    if plan.brief and plan.brief.caption_mode == "every_word":
        # Every-word captions are what a talking reel is read by: moved or shortened, never removed.
        structural |= {c.id for c in plan.captions}
    drop = {a.id for a in actions if a.action == "drop" and a.id not in structural}
    for action in actions:
        item = plan.find(action.id)
        if item is None or action.action == "keep" or action.id in drop:
            continue
        if action.action == "shorten" and hasattr(item, "end"):
            item.end = round(item.start + max(0.8, (item.end - item.start) * 0.6), 3)
            changed += 1
        elif action.action in ("enlarge", "shrink") and getattr(item, "box", None):
            # Grown or shrunk about its centre, kept inside the frame; the next pass draws it at the new size.
            from reel_engine.media import H, W

            k = 1.2 if action.action == "enlarge" else 0.8
            x, y, w, h = item.box
            nw, nh = min(W, round(w * k)), min(H, round(h * k))
            item.box = [max(0, min(W - nw, round(x + (w - nw) / 2))), max(0, min(H - nh, round(y + (h - nh) / 2))), nw, nh]
            changed += 1
        elif action.action == "move" and hasattr(item, "box"):
            # Re-laid from scratch next pass, starting from the opposite third of the frame.
            if item.box:
                item.box = [item.box[0], 300 if item.box[1] > 900 else 1350, item.box[2], item.box[3]]
            changed += 1
    before = len(plan.graphics) + len(plan.captions)
    plan.graphics = [g for g in plan.graphics if g.id not in drop]
    plan.captions = [c for c in plan.captions if c.id not in drop]
    return changed + before - len(plan.graphics) - len(plan.captions)
