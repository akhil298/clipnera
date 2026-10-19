"""A full edit: the whole video, edited the way an editor would, with nothing left out.

"Edit this video" is not "find the best 30 seconds". Everything said stays, in its order; what
goes is what an editor removes: dead air, filler words, false starts, earlier takes and talk not
meant for the audience (the analysis marks those, understanding/reading.py). Then the finish:
shots held closer in turn so the cuts read as angle changes, the key numbers on screen as they
are said, captions, and the source's own shape.

The plan is built here from the analysis, not by a model: a full edit is a known recipe, and the
model's part (what to cut, what is strong) was done reading the transcript.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from brain.context import EditContext
from brain.intent import IntentFrame
from brain.plan_ir import Aspect, MomentRef, PlanIR, PlanSection, PlanStep, PlanText
from brain.polish import number_phrase
from brain.route import RouteDecision
from understanding.mud import MUD

# Asked for something short, or a length: that is a cut-down, which the director plans.
_CUT_DOWN = re.compile(r"\b(shorts?|reels?|clips?|highlights?|trailer|teaser|tiktok|best (parts?|moments?|bits)|"
                       r"recap|summary|montage|\d+\s*(s|sec|secs|seconds?|min|mins|minutes?))\b", re.I)
ASPECT_RATIOS: dict[Aspect, float] = {"16:9": 16 / 9, "1:1": 1.0, "4:5": 4 / 5, "9:16": 9 / 16}
MOMENTS_PER_SECTION = 60
# One number on screen per this many seconds of the edit, at least two and at most twelve.
SECONDS_PER_CALLOUT = 30
CALLOUTS = (2, 12)
# Numbers on screen at least this far apart, so they don't crowd.
CALLOUT_GAP_SECONDS = 8.0
# Two videos whose words match this closely are the same footage (imported twice, or a copy).
SAME_SPEECH = 0.9


def wanted(prompt: str, decision: RouteDecision) -> bool:
    """A request to edit the video as a whole, not to cut it down to a short.

    Read from the user's words: the router fills in a length and a shape from the footage itself
    ("78 seconds", "9:16") when none was asked for.
    """
    return decision.intent == "new_edit" and not _CUT_DOWN.search(prompt)


def build(ctx: EditContext, *, subtitled: frozenset[str] = frozenset()) -> tuple[IntentFrame, PlanIR] | None:
    """The full edit of the project's spoken videos, or None when none has analysed speech. Footage in
    ``subtitled`` already has subtitles burned in, so it gets no captions over them."""
    videos = _distinct([(asset.id, ctx.muds[asset.id]) for asset in ctx.timeline.assets.values()
                        if asset.kind == "video" and asset.id in ctx.muds and ctx.muds[asset.id].utterances])
    if not videos:
        return None
    refs = [ref for asset_id, mud in videos for ref in _kept_runs(asset_id, mud)]
    sections = [PlanSection(section="body", moments=refs[n:n + MOMENTS_PER_SECTION])
                for n in range(0, len(refs), MOMENTS_PER_SECTION)]
    first = ctx.timeline.assets[videos[0][0]]
    aspect = _nearest(first.width / first.height) if first.width and first.height else None
    current = _nearest(ctx.timeline.width / ctx.timeline.height)
    callouts = _callouts(videos)
    trims = [t for _, mud in videos for t in mud.trims]
    dead_air = sum(s.t1 - s.t0 for _, mud in videos for s in mud.silences if s.kind == "dead_air")
    fillers = sum(1 for _, mud in videos for w in mud.words if w.filler)

    steps = [PlanStep(id="s1", kind="structure", intent="Lay down everything said, in order",
                      why=_removed_line(trims) or "Nothing was said twice or off-camera, so every line stays")]
    steps.append(PlanStep(id="s2", kind="tighten", intent="Cut the dead air and filler words", depends_on=["s1"],
                          why=f"{dead_air:.0f}s of dead air and {fillers} filler words", params={"style": "natural"}))
    last = "s2"
    if aspect and aspect != current:
        steps.append(PlanStep(id="s3", kind="reframe", intent=f"Keep the video's own {aspect} shape",
                              depends_on=[last], params={"aspect": aspect}))
        last = "s3"
    steps.append(PlanStep(id="s4", kind="zoom", intent="Hold every other shot closer so the cuts read as angle changes",
                          depends_on=[last], params={"style": "punch"}))
    if callouts:
        steps.append(PlanStep(id="s5", kind="callouts", depends_on=[last],
                              intent=f"Put {len(callouts)} key number{'' if len(callouts) == 1 else 's'} on screen as they are said"))
    captioned = not all(asset_id in subtitled for asset_id, _ in videos)
    if captioned:
        steps.append(PlanStep(id="s6", kind="captions", intent="Add captions", depends_on=[last]))
    if callouts:
        steps.append(PlanStep(id="s7", kind="sfx", intent="A pop on each number", depends_on=["s5"],
                              params={"on": "callouts"}))

    minutes = sum(mud.duration for _, mud in videos) / 60
    summary = (f"Full edit of {minutes:.1f} min: everything said stays; cuts {dead_air:.0f}s of dead air, "
               f"{fillers} filler words" + (f" and {len(trims)} false starts or retakes" if trims else "")
               + "; adds movement" + (", captions" if captioned else "") + (" and key numbers on screen" if callouts else "")
               + ("" if captioned else "; no captions, as the footage has its own subtitles") + ".")
    plan = PlanIR(strategy="chronological", title="Full edit", summary=summary[:240], aspect=aspect,
                  structure=sections, style={"pace": "medium", "captions": captioned, "tighten": "natural"},
                  text=callouts, steps=steps)
    frame = IntentFrame(scope="whole", aspect=aspect, assumptions=[
        "Everything said stays, in the order it was said",
        *([f"Keeps the footage's {aspect} shape"] if aspect else []),
    ])
    return frame, plan


def _distinct(videos: list[tuple[str, MUD]]) -> list[tuple[str, MUD]]:
    """The videos with the same footage brought in twice kept once (the first), so nothing is said twice."""
    kept: list[tuple[str, MUD, list[str]]] = []
    for asset_id, mud in videos:
        words = [w.text.lower().strip(".,!?") for w in mud.words]
        if not any(SequenceMatcher(None, words, other, autojunk=False).quick_ratio() >= SAME_SPEECH
                   and SequenceMatcher(None, words, other, autojunk=False).ratio() >= SAME_SPEECH for _, _, other in kept):
            kept.append((asset_id, mud, words))
    return [(asset_id, mud) for asset_id, mud, _ in kept]


def _nearest(ratio: float) -> Aspect:
    return min(ASPECT_RATIOS, key=lambda aspect: abs(ASPECT_RATIOS[aspect] - ratio))


def _kept_runs(asset_id: str, mud: MUD) -> list[MomentRef]:
    """Every sentence outside the analysis's cuts, as runs of consecutive sentences."""
    runs: list[MomentRef] = []
    start = end = None
    for line in mud.utterances:
        cut = any(trim.t0 <= line.t0 + 0.05 and line.t1 <= trim.t1 + 0.05 for trim in mud.trims)
        if cut:
            if start is not None:
                runs.append(MomentRef(asset=asset_id, words=[start, end]))
            start = None
            continue
        start = line.w0 if start is None else start
        end = line.w1
    if start is not None:
        runs.append(MomentRef(asset=asset_id, words=[start, end]))
    return runs


def _callouts(videos: list[tuple[str, MUD]]) -> list[PlanText]:
    """The numbers said in the strongest moments, spaced out, as many as the length warrants."""
    seconds = sum(mud.duration for _, mud in videos)
    limit = max(CALLOUTS[0], min(CALLOUTS[1], round(seconds / SECONDS_PER_CALLOUT)))
    found: list[tuple[str, float, PlanText]] = []
    ranked = sorted(((asset_id, mud, m) for asset_id, mud in videos for m in mud.moments if m.kind == "quote"),
                    key=lambda row: -row[2].score)
    for asset_id, mud, moment in ranked:
        words = [w for w in mud.words if w.t0 >= moment.t0 - 0.05 and w.t1 <= moment.t1 + 0.05
                 and not any(t.t0 <= w.t0 < t.t1 for t in mud.trims)]
        phrase = number_phrase(words)
        if phrase is None:
            continue
        text, first, last = phrase
        at = mud.words[first].t0
        if any(other == asset_id and abs(at - t) < CALLOUT_GAP_SECONDS for other, t, _ in found):
            continue
        found.append((asset_id, at, PlanText(kind="callout", content=text,
                                             anchor=MomentRef(asset=asset_id, words=[first, last]))))
        if len(found) == limit:
            break
    return [text for _, _, text in sorted(found, key=lambda row: (row[0], row[1]))]


def _removed_line(trims: list) -> str:
    if not trims:
        return ""
    kinds = {"false_start": "false starts", "retake": "earlier takes", "off_script": "off-camera talk"}
    named = sorted({kinds[t.kind] for t in trims})
    return f"Leaves out {len(trims)} stretch{'es' if len(trims) != 1 else ''} of " + ", ".join(named)
