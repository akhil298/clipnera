"""Which word of a clip gets which graphic: one model call proposes, the words decide.

The model reads a batch of clips as ``id:word`` and answers with beats
anchored to word ids (it never writes times). Each beat is then checked the
way motion graphics are (:mod:`motion.moments`): its texts must be made of
the words it points at, its figures must match digit for digit, an asset is
only used when its trigger word was said, and anything unproven is dropped
or turned into a plainer kind. Code then times the survivors and keeps a
paced set: one every few seconds, never two at once, cards spaced out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from beats import kit
from beats.plan import (
    BEHIND,
    BESIDE,
    CARD,
    CHART,
    COUNT_UP,
    CTA,
    FLOW,
    IMAGE,
    KEYWORD,
    KINDS,
    LIST,
    LIST_MARKS,
    LOGO,
    MAP,
    NAME,
    OBJECT,
    PANEL,
    PLACES,
    STATEMENT,
    TRENDS,
    UI,
    UI_VARIANTS,
    Beat,
    BeatPlan,
)
from broll.planner import ClipWords
from core.logging_config import get_logger
from motion.moments import _clean, _digits_said, _said, tokens
from skills import GRAPHIC_BEATS, skill_block

log = get_logger(__name__)

THEMES = ("clean", "dark", "editorial", "bold")
MAX_WORDS_PER_CLIP = 450
MAX_SPAN_WORDS = 24
MIN_ITEMS, MAX_ITEMS = 3, 6
MAX_TEXT_CHARS = {KEYWORD: 28, STATEMENT: 48, NAME: 30, LOGO: 30, MAP: 30, CTA: 20, COUNT_UP: 16}
MAX_ITEM_CHARS = 30
MAX_LABEL_CHARS = 28
MAX_STATEMENT_WORDS = 7
# Seconds of clip per beat at most, and the air kept between two beats.
SECONDS_PER_BEAT = 2.4
GAP_SECONDS = 0.25
OPENING_SECONDS = 0.6
# A card (or anything placed as one) replaces the speaker: at most one per this many seconds.
CARD_SPACING_SECONDS = 5.0
LEAD_SECONDS = 0.08
# (shortest, longest) seconds on screen, after the last anchored word is said.
HOLD = {
    COUNT_UP: (1.6, 2.6), LIST: (1.2, 6.5), LOGO: (1.4, 2.2), NAME: (1.6, 2.4), KEYWORD: (1.0, 2.0),
    STATEMENT: (1.6, 2.8), OBJECT: (1.2, 2.2), CHART: (2.0, 3.0), FLOW: (1.2, 6.5), UI: (2.0, 4.0),
    IMAGE: (1.6, 3.2), CTA: (2.0, 3.0), MAP: (2.0, 3.0),
}
# Most useful first: a weaker beat loses a clash.
PRIORITY = {kind: rank for rank, kind in enumerate(
    (CTA, COUNT_UP, LIST, LOGO, STATEMENT, IMAGE, CHART, FLOW, UI, OBJECT, MAP, NAME, KEYWORD)
)}
_FIGURE = re.compile(r"^(?P<prefix>[^\d]*)(?P<number>\d[\d,]*(?:\.\d+)?)(?P<suffix>.*)$")

SYSTEM = f"""You are a premium short-form video editor. For each clip you choose the graphic beats: which spoken words get which on-screen graphic. You return JSON only.

Each clip is its index, its category, then its words as id:word. A beat points at the words it shows with `first` and `last` (word ids, inclusive). Fields:
- kind: one of {", ".join(KINDS)}.
- text: what the graphic shows, in the speaker's own words (numbers as digits). Empty when the kind needs none.
- label: a short second line from the speech (a figure's unit, a list's title, a keyword's lead words). Often empty.
- place: card (fills the frame), behind (big, behind the speaker), beside (near the head), panel (a box in the free part of the frame).
- items: for list, flow and ui checklist/notification: each item's word range and its text (at most 4 words). Otherwise empty.
- mark: for list: check, cross or none. Otherwise none.
- visual: for object, image and ui: what to show, in plain words the speaker used (ui: search, notification, chat or checklist). Otherwise empty.
- trend: for chart: up or down. Otherwise none.
- why: 3-8 words on why this line earns the beat.
And per clip a `theme`: {", ".join(THEMES)}.

{skill_block(GRAPHIC_BEATS)}"""


class _Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first: int
    last: int
    text: str


class _Beat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[KINDS]
    first: int
    last: int
    text: str
    label: str
    place: Literal[PLACES]
    items: list[_Item]
    mark: Literal[LIST_MARKS]
    visual: str
    trend: Literal[TRENDS]
    why: str


class _Clip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    theme: Literal[THEMES]
    beats: list[_Beat]


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clips: list[_Clip]


@dataclass(frozen=True)
class Body:
    """Where a clip plays in the source: its stitched spans, in source seconds."""

    spans: list[tuple[float, float]]

    @property
    def start(self) -> float:
        return self.spans[0][0]

    @property
    def seconds(self) -> float:
        return sum(end - start for start, end in self.spans)

    def holds(self, start: float, end: float) -> bool:
        return any(a - 1e-3 <= start and end <= b + 1e-3 for a, b in self.spans)


def prompt(clips: list[ClipWords], categories: list[str]) -> str:
    blocks = []
    for index, clip in enumerate(clips):
        words = " ".join(f"{i}:{w['word'].strip()}" for i, w in enumerate(clip.words[:MAX_WORDS_PER_CLIP]))
        category = categories[index] if index < len(categories) else ""
        blocks.append(f"[{index}] category: {category or 'unknown'}. {words}")
    return "Plan the graphic beats for each clip.\n\n" + "\n\n".join(blocks) + "\n\nReturn JSON only."


async def plan_beats(clips: list[ClipWords], client: Any, categories: list[str]) -> list[BeatPlan]:
    """One checked, paced plan per clip, in order; a failed call gives empty plans."""
    if not clips:
        return []
    reply = await client.chat_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt(clips, categories)}],
        _Reply, max_tokens=1400 * len(clips) + 400,
    )
    by_index = {clip.index: clip for clip in reply.clips}
    plans = []
    for index, clip in enumerate(clips):
        raw = by_index.get(index)
        if raw is None or not clip.words:
            plans.append(BeatPlan())
            continue
        body = Body(list(clip.spans))
        words = clip.words[:MAX_WORDS_PER_CLIP]
        proven = [beat for beat in (prove(item, words) for item in raw.beats) if beat is not None]
        plans.append(BeatPlan(theme=raw.theme, beats=pace(proven, body)))
    return plans


def prove(raw: _Beat, words: list[dict[str, Any]]) -> Beat | None:
    """The model's beat as a timed :class:`Beat`, or ``None`` when its words do not prove it."""
    span = _span(raw.first, raw.last, words)
    if span is None:
        return None
    first, last = span
    check = _CHECKS.get(raw.kind)
    built = check(raw, words, first, last) if check else None
    if built is None:
        return None
    kind, data, place, asset, steps = built
    start = float(words[first]["start"]) - LEAD_SECONDS
    said_end = max([float(words[last]["end"]), *steps])
    shortest, longest = HOLD[kind]
    end = min(max(start + shortest, said_end + 0.6), max(said_end, start) + longest)
    return Beat(kind=kind, start=round(start, 3), end=round(end, 3), place=place, data=data,
                steps=[round(t, 3) for t in steps], asset=asset, why=_clean(raw.why, 80))


def pace(beats: list[Beat], body: Body) -> list[Beat]:
    """The beats a clip keeps: inside its body, spaced, at most one per ``SECONDS_PER_BEAT``."""
    budget = max(1, int(body.seconds // SECONDS_PER_BEAT))
    kept: list[Beat] = []
    for beat in sorted(beats, key=lambda b: (PRIORITY[b.kind], b.start)):
        if len(kept) >= budget:
            break
        if beat.start < body.start + OPENING_SECONDS or not body.holds(beat.start, beat.end):
            continue
        if any(beat.start < other.end + GAP_SECONDS and other.start < beat.end + GAP_SECONDS for other in kept):
            continue
        if _is_card(beat) and any(_is_card(other) and abs(other.start - beat.start) < CARD_SPACING_SECONDS for other in kept):
            continue
        kept.append(beat)
    return sorted(kept, key=lambda b: b.start)


def _is_card(beat: Beat) -> bool:
    return beat.place == CARD or beat.kind in (STATEMENT, IMAGE)


# --- per-kind proofs: (kind, data, place, asset path, step times) or None -------------------------

Built = tuple[str, dict[str, Any], str, str, list[float]]


def _said_text(words: list[dict[str, Any]], first: int, last: int, pad: int = 0) -> str:
    return " ".join(w["word"] for w in words[max(0, first - pad):min(len(words), last + pad + 1)])


def _label(raw: _Beat, words: list[dict[str, Any]], first: int, last: int, pad: int = 8) -> str:
    label = _clean(raw.label, MAX_LABEL_CHARS)
    if label and _said(label, words, max(0, first - pad), min(len(words) - 1, last + pad)):
        return label
    return ""


def _place(raw: _Beat, allowed: tuple[str, ...], default: str) -> str:
    return raw.place if raw.place in allowed else default


def _asset(entry: dict[str, Any] | None) -> str:
    return str(entry.get("path") or "") if entry else ""


def _count_up(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    value = _clean(raw.text, MAX_TEXT_CHARS[COUNT_UP])
    figure = _FIGURE.match(value)
    if not figure:
        return None
    digits = re.sub(r"\D", "", figure["number"])
    said = "".join(t for t in tokens(_said_text(words, first, last)) if t.isdigit())
    if not _digits_said(digits, said, words, (first, last)):
        return None
    data = {"prefix": figure["prefix"].strip(), "number": figure["number"], "suffix": figure["suffix"].strip(),
            "label": _label(raw, words, first, last)}
    return COUNT_UP, data, _place(raw, (BEHIND, BESIDE, CARD), BESIDE), "", []


def _items(raw: _Beat, words: list[dict[str, Any]], least: int) -> list[tuple[float, str]] | None:
    items: list[tuple[float, str]] = []
    for item in raw.items[:MAX_ITEMS]:
        span = _span(item.first, item.last, words)
        text = _clean(item.text, MAX_ITEM_CHARS)
        if span is None or not text or not _said(text, words, *span):
            return None  # One unproven item and the whole list is suspect.
        items.append((float(words[span[0]]["start"]), text))
    if len(items) < least or any(b[0] <= a[0] for a, b in zip(items, items[1:])):
        return None
    return items


def _list(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    items = _items(raw, words, MIN_ITEMS)
    if items is None:
        return None
    data = {"title": _label(raw, words, first, last), "items": [text for _, text in items], "mark": raw.mark}
    return LIST, data, _place(raw, (PANEL, CARD), PANEL), "", [t for t, _ in items]


def _flow(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    items = _items(raw, words, MIN_ITEMS)
    if items is None:
        return None
    data = {"title": _label(raw, words, first, last), "items": [text for _, text in items[:5]]}
    return FLOW, data, _place(raw, (PANEL, CARD), PANEL), "", [t for t, _ in items[:5]]


def _exact(raw: _Beat, words: list[dict[str, Any]], first: int, last: int, kind: str) -> str:
    text = _clean(raw.text, MAX_TEXT_CHARS.get(kind, MAX_LABEL_CHARS))
    return text if text and _said(text, words, first, last, exact=True) else ""


def _logo(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    name = _exact(raw, words, first, last, LOGO)
    if not name:
        return None
    entry = kit.logo(name)
    if entry is None:
        return _name(raw, words, first, last)
    return LOGO, {"text": name}, BESIDE, _asset(entry), []


def _name(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    name = _exact(raw, words, first, last, NAME)
    if not name:
        return None
    return NAME, {"text": name, "label": _label(raw, words, first, last)}, BESIDE, "", []


def _map(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    place = _exact(raw, words, first, last, MAP)
    if not place:
        return None
    entry = kit.find(("map",), _said_text(words, first, last), place)
    if entry is None:
        return _name(raw, words, first, last)
    return MAP, {"text": place, "label": _label(raw, words, first, last)}, _place(raw, (PANEL, CARD), PANEL), _asset(entry), []


def _keyword(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    text = _exact(raw, words, first, last, KEYWORD)
    if not text or len(text.split()) > 4:
        return None
    lead = _clean(raw.label, MAX_LABEL_CHARS)
    lead = lead if lead and _said(lead, words, max(0, first - 6), last) else ""
    return KEYWORD, {"text": text, "lead": lead}, _place(raw, (BEHIND, BESIDE), BEHIND), "", []


def _statement(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    text = _clean(raw.text, MAX_TEXT_CHARS[STATEMENT])
    if not text or len(text.split()) > MAX_STATEMENT_WORDS or not _said(text, words, first, last):
        return None
    return STATEMENT, {"text": text, "label": _label(raw, words, first, last)}, CARD, "", []


def _object(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    entry = kit.find(("object3d",), _said_text(words, first, last, pad=3), raw.visual)
    if entry is None:
        return _keyword(raw, words, first, last)
    return OBJECT, {"text": _label(raw, words, first, last) or _exact(raw, words, first, last, KEYWORD)}, BESIDE, _asset(entry), []


def _chart(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    if raw.trend == "none":
        return None
    label = _label(raw, words, first, last) or _exact(raw, words, first, last, KEYWORD)
    figures = [t for t in tokens(_said_text(words, first, last)) if t.isdigit()][:4]
    return CHART, {"trend": raw.trend, "label": label, "figures": figures}, _place(raw, (PANEL, CARD), PANEL), "", []


def _ui(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    variant = raw.visual.strip().lower()
    if variant not in UI_VARIANTS:
        return None
    text = _clean(raw.text, MAX_LABEL_CHARS * 2)
    text = text if text and _said(text, words, first, last) else ""
    items = _items(raw, words, 1) if raw.items else []
    if items is None or not (text or items):
        return None
    data = {"variant": variant, "text": text, "items": [t for _, t in items or []]}
    return UI, data, _place(raw, (PANEL, CARD), PANEL), "", [t for t, _ in items or []]


def _image(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    entry = kit.find(("still",), _said_text(words, first, last, pad=4), raw.visual)
    if entry is None:
        return _statement(raw, words, first, last) if raw.text else None
    caption = _clean(raw.text, MAX_TEXT_CHARS[STATEMENT])
    caption = caption if caption and _said(caption, words, first, last) else ""
    return IMAGE, {"text": caption}, CARD, _asset(entry), []


def _cta(raw: _Beat, words: list[dict[str, Any]], first: int, last: int) -> Built | None:
    text = _exact(raw, words, first, last, CTA).upper()
    said = _said_text(words, first, last).lower()
    verb = next((v for v in ("comment", "dm", "follow", "subscribe", "link", "share", "save") if v in said), "")
    if not verb:
        return None
    return CTA, {"verb": verb.upper(), "text": text}, PANEL, "", []


_CHECKS = {
    COUNT_UP: _count_up, LIST: _list, FLOW: _flow, LOGO: _logo, NAME: _name, MAP: _map, KEYWORD: _keyword,
    STATEMENT: _statement, OBJECT: _object, CHART: _chart, UI: _ui, IMAGE: _image, CTA: _cta,
}


def _span(first: int, last: int, words: list[dict[str, Any]]) -> tuple[int, int] | None:
    if not (0 <= first <= last < len(words)) or last - first > MAX_SPAN_WORDS:
        return None
    return first, last
