"""From proven moments to the graphics a clip actually gets.

Each moment kind maps to one template. A cue is only kept when it passes the
editorial gates, checked here in order:

* value: a list needs 3+ items; a name is tagged once per clip; a reaction
  sticker only fits a funny, hype or wholesome clip;
* time: on screen long enough to read, never in the clip's first second;
* budget: at most one graphic per ``SECONDS_PER_CUE`` of clip, never two on
  screen at once, with a breath between them; the most useful kinds win.

Where on screen a cue goes is decided at render time, from the layout the cut
actually has there (see :mod:`motion.graphics`).
"""

from __future__ import annotations

from motion.icons import icon_for
from motion.moments import ClipMoments, Moment
from motion.plan import BIG_NUMBER, CTA_CARD, ENTITY_TAG, LIST_CARD, REACTION, Cue, MotionPlan

# Seconds of clip per graphic, at most.
SECONDS_PER_CUE = 6.0
# Clear air between two graphics.
GAP_SECONDS = 1.0
# Nothing in the opening second: the hook and title land first.
OPENING_SECONDS = 1.0
# Reading time: a base plus this much per word shown.
READ_BASE_SECONDS = 1.0
READ_PER_WORD_SECONDS = 0.3
MAX_HOLD_SECONDS = {LIST_CARD: 3.0, BIG_NUMBER: 2.2, ENTITY_TAG: 2.2, CTA_CARD: 3.5, REACTION: 1.2}
MIN_HOLD_SECONDS = {LIST_CARD: 1.5, BIG_NUMBER: 1.6, ENTITY_TAG: 1.6, CTA_CARD: 2.5, REACTION: 0.9}
# Most useful first; a weaker cue loses a clash.
PRIORITY = {"cta": 0, "list": 1, "number": 2, "name": 3, "reaction": 4}
TEMPLATE = {"list": LIST_CARD, "number": BIG_NUMBER, "name": ENTITY_TAG, "cta": CTA_CARD, "reaction": REACTION}
REACTION_EMOJI = {"funny": "😂", "hype": "🔥", "wholesome": "🥹"}
MAX_REACTIONS = 2
NAME_ICONS = {"place": "📍", "person": "👤", "brand": "🏷️", "product": "🏷️", "game": "🎮"}
CTA_LABELS = {
    "code": "USE CODE", "link": "LINK IN BIO", "follow": "FOLLOW FOR MORE",
    "comment": "COMMENT", "subscribe": "SUBSCRIBE",
}


def plan_motion(found: ClipMoments, body_start: float, body_end: float, body_seconds: float) -> MotionPlan:
    """The clip's graphics: one cue per moment that passes every gate.

    ``body_start``/``body_end`` bound the clip in source seconds and
    ``body_seconds`` is how long it plays (stitched clips skip time).
    """
    budget = max(1, int(body_seconds // SECONDS_PER_CUE))
    candidates = [cue for cue in (_cue(m, found.mood) for m in found.moments) if cue is not None]
    kept: list[Cue] = []
    names = reactions = 0
    for cue, moment in sorted(candidates, key=lambda pair: (PRIORITY[pair[1].kind], pair[0].start)):
        if len(kept) >= budget:
            break
        if cue.start < body_start + OPENING_SECONDS or cue.end > body_end + MAX_HOLD_SECONDS[cue.kind]:
            continue
        if any(cue.start < other.end + GAP_SECONDS and other.start < cue.end + GAP_SECONDS for other in kept):
            continue
        if moment.kind == "name":
            if names:
                continue
            names += 1
        if moment.kind == "reaction":
            if reactions >= MAX_REACTIONS:
                continue
            reactions += 1
        kept.append(cue)
    return MotionPlan(mood=found.mood, cues=sorted(kept, key=lambda cue: cue.start))


def _cue(moment: Moment, mood: str) -> tuple[Cue, Moment] | None:
    kind = TEMPLATE[moment.kind]
    if moment.kind == "list":
        items = [{"text": text, "icon": icon_for(text)} for text in moment.data["items"]]
        data = {"title": moment.data["title"], "items": items}
        shown = [moment.data["title"], *moment.data["items"]]
        # The card arrives with the first item and stays until the last can be read.
        start, end = moment.beats[0] - 0.15, moment.end + _hold(kind, shown[-1:])
        return Cue(kind, round(start, 3), round(end, 3), data, list(moment.beats), "list read out"), moment
    if moment.kind == "number":
        data = {"value": moment.data["value"], "label": moment.data.get("label", "")}
        return _timed(kind, moment, data, [data["value"], data["label"]], "a figure that matters")
    if moment.kind == "name":
        data = {"text": moment.data["text"], "icon": NAME_ICONS[moment.data["kind"]]}
        return _timed(kind, moment, data, [data["text"]], f"{moment.data['kind']} named")
    if moment.kind == "cta":
        data = {"label": CTA_LABELS[moment.data["kind"]], "value": moment.data.get("text", "")}
        return _timed(kind, moment, data, [data["label"], data["value"]], "call to action")
    if moment.kind == "reaction":
        emoji = REACTION_EMOJI.get(mood)
        if not emoji:
            return None
        return _timed(kind, moment, {"emoji": emoji}, [], "loud reaction")
    return None


def _timed(kind: str, moment: Moment, data: dict, shown: list[str], why: str) -> tuple[Cue, Moment]:
    start = moment.start - 0.1
    return Cue(kind, round(start, 3), round(start + _hold(kind, shown), 3), data, [], why), moment


def _hold(kind: str, shown: list[str]) -> float:
    words = sum(len(text.split()) for text in shown if text)
    return min(MAX_HOLD_SECONDS[kind], max(MIN_HOLD_SECONDS[kind], READ_BASE_SECONDS + READ_PER_WORD_SECONDS * words))
