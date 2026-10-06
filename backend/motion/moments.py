"""Moments in a clip worth a graphic, with the words that prove them.

One LLM call reads a batch of clips and points at word ranges: a list read
out, a number that matters, a place, person or brand named, a call to action,
and the clip's mood. Its answer is evidence to check, not a decision: every
text a graphic will show must be made of the words in its range, numbers must
match digit for digit, and anything that fails is dropped. Loud reactions
(laughs, screams) come from the audio, not the model.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from broll.planner import ClipWords
from core.logging_config import get_logger
from skills import MOTION_GRAPHICS, skill_block

log = get_logger(__name__)

MOODS = ("funny", "hype", "wholesome", "serious", "sad", "neutral")
ENTITY_KINDS = ("place", "person", "brand", "product", "game")
CTA_KINDS = ("code", "link", "follow", "comment", "subscribe")
MAX_WORDS_PER_CLIP = 400
MIN_LIST_ITEMS = 3
MAX_LIST_ITEMS = 6
# A list read out over longer than this is a story, not a list.
MAX_LIST_SECONDS = 18.0
MAX_ITEM_CHARS = 26
MAX_LABEL_CHARS = 22
# Share of a graphic text's words that must be found in its word range.
MIN_WORD_MATCH = 0.8
# Loudness (z against the surrounding minute) of a reaction worth a sticker.
REACTION_Z = 2.5
LAUGH_WORDS = frozenset({"haha", "hahaha", "ha", "lol", "lmao", "laughs", "laughing", "laughter"})

SYSTEM = """You are a short-form video editor deciding where on-screen graphics help a viewer. You return valid JSON only.

Read each clip's words and report only what is clearly there:
- lists: the speaker names 3-6 items of one kind in a row (an order, steps, reasons, ingredients, a top 3). Give a short title (2-4 words, from the speech or a plain label like "The order") and each item's word range and text. Item text is the speaker's own words, shortened to at most 4 words; write numbers as digits.
- numbers: a figure that is the point of what is said (money, a count, a record, a percentage, a multiplier), not a passing one ("two minutes ago", "one time"). Give the value as it should be shown ("$10,000", "200", "3x", "90%") and a 1-3 word label from the speech.
- names: a specific place, person, brand, product or game the viewer may not know, said once clearly. Not the speaker or the person they are talking to.
- ctas: the speaker asks viewers to do something: use a code, visit a link, follow, comment a word, subscribe. Give the code or word exactly as said, in capitals.
- mood: the clip's overall tone: funny, hype, wholesome, serious, sad or neutral. Judge it as a viewer would: "(LOUD)" after a word marks a burst of laughter, cheering or shouting heard right there, and the clip's category is given. Mock anger, roasting and teasing that gets laughs is funny, not serious.

Word ranges use the word ids shown (from/to inclusive). Leave a list empty rather than stretch it. Most clips have no list and no cta."""

# The motion planner reads its editing skill before it plans (backend/skills).
SYSTEM = f"{SYSTEM}\n\n{skill_block(MOTION_GRAPHICS)}"

EXAMPLE = (
    '{"clips":[{"index":0,"mood":"funny",'
    '"lists":[{"title":"The order","items":[{"from":12,"to":14,"text":"12 pcs wings"},{"from":16,"to":17,"text":"large pickle"},'
    '{"from":19,"to":20,"text":"BBQ sauce"}]}],'
    '"numbers":[{"from":40,"to":42,"value":"$10,000","label":"in one day"}],'
    '"names":[{"from":55,"to":56,"kind":"place","text":"Lagos"}],'
    '"ctas":[{"from":80,"to":84,"kind":"code","text":"KFSPEED"}]}]}'
)

_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
    "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90",
    "hundred": "100", "thousand": "1000", "million": "1000000", "billion": "1000000000",
}
_TOKEN = re.compile(r"[a-z0-9]+")
# Short forms a graphic may use for a spoken word.
ABBREVIATIONS = {
    "pcs": "piece", "pc": "piece", "lg": "large", "med": "medium", "sm": "small", "hrs": "hour", "hr": "hour",
    "mins": "minute", "min": "minute", "secs": "second", "sec": "second", "yrs": "year", "yr": "year",
    "w": "with", "n": "and",
}


@dataclass(frozen=True)
class Moment:
    kind: str  # list | number | name | cta | reaction
    start: float
    end: float
    data: dict[str, Any] = field(default_factory=dict)
    beats: tuple[float, ...] = ()


@dataclass
class ClipMoments:
    mood: str = "neutral"
    moments: list[Moment] = field(default_factory=list)


def tokens(text: str) -> list[str]:
    """Lower-case words with number words as digits, so "twelve" matches "12"."""
    out: list[str] = []
    for token in _TOKEN.findall(text.lower().replace(",", "")):
        out.append(_NUMBER_WORDS.get(token, token))
    return out


def _forms(token: str) -> set[str]:
    """A word and its singular, so "pieces" matches "piece"."""
    forms = {token}
    if len(token) > 3 and token.endswith("es"):
        forms.add(token[:-2])
    if len(token) > 2 and token.endswith("s"):
        forms.add(token[:-1])
    return forms


def prompt(clips: list[ClipWords], categories: list[str] | None = None, loud: list[list[float]] | None = None) -> str:
    blocks = []
    for index, clip in enumerate(clips):
        marked = _loud_word_ids(clip.words[:MAX_WORDS_PER_CLIP], (loud or [])[index] if loud and index < len(loud) else [])
        words = " ".join(
            f"{i}:{w['word']}" + (" (LOUD)" if i in marked else "") for i, w in enumerate(clip.words[:MAX_WORDS_PER_CLIP])
        )
        category = (categories or [])[index] if categories and index < len(categories) else ""
        blocks.append(f"[{index}]" + (f" category: {category}." if category else "") + f" {words}")
    return (
        "Each clip is its index, then its words as id:word.\n\n" + "\n\n".join(blocks)
        + f"\n\nReturn JSON only, one entry per clip, like: {EXAMPLE}"
    )


async def find_moments(
    clips: list[ClipWords], client: Any, categories: list[str] | None = None, loud: list[list[float]] | None = None,
) -> list[ClipMoments]:
    """Checked moments per clip, in order; an unusable answer gives none.

    ``categories`` (the clips' content kinds) and ``loud`` (per clip, source
    seconds of loud reactions) let the model judge the mood as a viewer hears it.
    """
    if not clips:
        return []
    response = await client.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt(clips, categories, loud)}],
        temperature=0.2, max_tokens=400 * len(clips) + 200, json_mode=True,
    )
    try:
        data = json.loads(response[response.find("{"): response.rfind("}") + 1])
    except (ValueError, TypeError) as exc:
        log.warning("Motion moments: unreadable JSON: %s", exc)
        return [ClipMoments() for _ in clips]
    by_index = {item.get("index"): item for item in data.get("clips", []) if isinstance(item, dict)}
    return [validate(by_index.get(index) or {}, clip) for index, clip in enumerate(clips)]


def validate(raw: dict[str, Any], clip: ClipWords) -> ClipMoments:
    """The model's answer for one clip, keeping only what its words prove."""
    words = clip.words[:MAX_WORDS_PER_CLIP]
    mood = str(raw.get("mood") or "neutral").lower()
    found = ClipMoments(mood=mood if mood in MOODS else "neutral")
    for item in _dicts(raw.get("lists")):
        moment = _list(item, words)
        if moment:
            found.moments.append(moment)
    for item in _dicts(raw.get("numbers")):
        moment = _number(item, words)
        if moment:
            found.moments.append(moment)
    for item in _dicts(raw.get("names")):
        moment = _name(item, words)
        if moment:
            found.moments.append(moment)
    for item in _dicts(raw.get("ctas")):
        moment = _cta(item, words)
        if moment:
            found.moments.append(moment)
    found.moments.sort(key=lambda m: m.start)
    return found


def _list(item: dict[str, Any], words: list[dict[str, Any]]) -> Moment | None:
    items = []
    for entry in _dicts(item.get("items"))[:MAX_LIST_ITEMS]:
        span = _span(entry, words)
        text = _clean(entry.get("text"), MAX_ITEM_CHARS)
        if span is None or not text or not _said(text, words, *span):
            return None  # One unproven item and the whole list is suspect.
        items.append((float(words[span[0]]["start"]), float(words[span[1]]["end"]), text))
    if len(items) < MIN_LIST_ITEMS:
        return None
    items.sort()
    if any(b[0] < a[0] for a, b in zip(items, items[1:])) or items[-1][1] - items[0][0] > MAX_LIST_SECONDS:
        return None
    title = _clean(item.get("title"), MAX_LABEL_CHARS) or "The list"
    return Moment(
        "list", items[0][0], items[-1][1],
        {"title": title, "items": [text for _, _, text in items]},
        tuple(round(start, 3) for start, _, _ in items),
    )


def _number(item: dict[str, Any], words: list[dict[str, Any]]) -> Moment | None:
    span = _span(item, words)
    value = _clean(item.get("value"), 14)
    if span is None or not value:
        return None
    digits = re.sub(r"\D", "", value)
    said = "".join(t for t in tokens(" ".join(w["word"] for w in words[span[0]:span[1] + 1])) if t.isdigit())
    if not digits or not _digits_said(digits, said, words, span):
        return None
    label = _clean(item.get("label"), MAX_LABEL_CHARS)
    if label and not _said(label, words, max(0, span[0] - 6), min(len(words) - 1, span[1] + 6)):
        label = ""
    return Moment("number", float(words[span[0]]["start"]), float(words[span[1]]["end"]), {"value": value, "label": label})


def _digits_said(digits: str, said: str, words: list[dict[str, Any]], span: tuple[int, int]) -> bool:
    """Whether the shown figure is what was said: its digits, or spoken as words ("ten thousand")."""
    if digits in said:
        return True
    spoken = tokens(" ".join(w["word"] for w in words[span[0]:span[1] + 1]))
    return _words_value(spoken) == int(digits)


def _words_value(spoken: list[str]) -> int | None:
    """``["10", "1000"]`` -> 10000: numbers said as words, multiplied out."""
    total, current, seen = 0, 0, False
    for token in spoken:
        if not token.isdigit():
            continue
        value, seen = int(token), True
        if value in (100, 1000, 1000000, 1000000000):
            current = max(1, current) * value
            if value >= 1000:
                total, current = total + current, 0
        else:
            current += value
    return total + current if seen else None


def _name(item: dict[str, Any], words: list[dict[str, Any]]) -> Moment | None:
    span = _span(item, words)
    kind = str(item.get("kind") or "").lower()
    text = _clean(item.get("text"), MAX_LABEL_CHARS)
    if span is None or kind not in ENTITY_KINDS or not text or not _said(text, words, *span, exact=True):
        return None
    return Moment("name", float(words[span[0]]["start"]), float(words[span[1]]["end"]), {"kind": kind, "text": text})


def _cta(item: dict[str, Any], words: list[dict[str, Any]]) -> Moment | None:
    span = _span(item, words)
    kind = str(item.get("kind") or "").lower()
    text = _clean(item.get("text"), MAX_LABEL_CHARS).upper()
    if span is None or kind not in CTA_KINDS:
        return None
    if text and not _said(text, words, *span, exact=True):
        return None
    if kind in ("code", "comment") and not text:
        return None
    return Moment("cta", float(words[span[0]]["start"]), float(words[span[1]]["end"]), {"kind": kind, "text": text})


def reactions(loudness: Any, words: list[dict[str, Any]], spans: list[tuple[float, float]]) -> list[Moment]:
    """Loud bursts with no speech over them (a laugh, a scream), from the source's loudness."""
    if loudness is None:
        return []
    found: list[Moment] = []
    for start, end in spans:
        for t, z in loudness.peaks():
            if not (start <= t < end) or z < REACTION_Z:
                continue
            spoken = [w for w in words if float(w["start"]) - 0.2 <= t <= float(w["end"]) + 0.2]
            if all(tokens(w["word"])[:1] and tokens(w["word"])[0] in LAUGH_WORDS for w in spoken):
                if not found or t - found[-1].start > 3.0:
                    found.append(Moment("reaction", t, t + 1.2, {"z": round(z, 2)}))
    return found


def _loud_word_ids(words: list[dict[str, Any]], loud: list[float]) -> set[int]:
    """Ids of the words each loud moment follows (the last word started before it)."""
    ids = set()
    for t in loud:
        before = [i for i, w in enumerate(words) if float(w["start"]) <= t]
        if before:
            ids.add(before[-1])
    return ids


def loud_moments(loudness: Any, spans: list[tuple[float, float]]) -> list[float]:
    """Source seconds inside ``spans`` where the audio bursts (laughs, cheers, shouts)."""
    if loudness is None:
        return []
    return [t for t, z in loudness.peaks() if z >= REACTION_Z and any(a <= t < b for a, b in spans)]


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _span(item: dict[str, Any], words: list[dict[str, Any]]) -> tuple[int, int] | None:
    try:
        first, last = int(item.get("from")), int(item.get("to"))
    except (TypeError, ValueError):
        return None
    if not (0 <= first <= last < len(words)) or last - first > 12:
        return None
    return first, last


def _clean(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip(".,!?;:\"'")
    return text if 0 < len(text) <= limit else ""


def _said(text: str, words: list[dict[str, Any]], first: int, last: int, exact: bool = False) -> bool:
    """Whether ``text`` is made of the words ``first..last`` (number words count as digits).

    ``exact`` needs every word; otherwise ``MIN_WORD_MATCH`` of them, which
    allows a joined "pcs" or a dropped "the" in a shortened list item. Digits
    must always be there.
    """
    said = {form for token in tokens(" ".join(w["word"] for w in words[first:last + 1])) for form in _forms(token)}
    joined = "".join(tokens(" ".join(w["word"] for w in words[first:last + 1])))
    shown = [ABBREVIATIONS.get(t, t) for t in tokens(text)]
    if not shown:
        return False
    found = [t for t in shown if _forms(t) & said or (len(t) > 2 and t in joined)]
    if any(t.isdigit() and t not in found for t in shown):
        return False
    return len(found) == len(shown) if exact else len(found) >= MIN_WORD_MATCH * len(shown)
