"""Where a clip should cut away to B-roll, and what to show.

One LLM call covers a batch of clips. The model points at word ranges where
the speaker names something the viewer could be shown (a place, an object, an
activity) and writes an English search query for it; a validator then turns
those ranges into timings that respect the editing rules. A clip that is about
the person -- a confession, an emotional story, a joke landing on their face --
gets no cutaways and is simply edited well.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)

MIN_CUTAWAY_SECONDS = 1.5
MAX_CUTAWAY_SECONDS = 4.0
# The hook and first line stay on the speaker's face.
NO_CUTAWAY_BEFORE_SECONDS = 2.0
MIN_GAP_SECONDS = 1.5
MAX_COVERAGE = 0.4
MAX_WORDS_PER_CLIP = 400

SYSTEM = """You are a short-form video editor adding B-roll cutaways to talking-head clips. You return valid JSON only.

A cutaway briefly replaces the speaker with footage of what they are talking about. Add one only where the speaker names something concrete that footage can show: a place (a city, an office, a beach), an object (money, a phone, food), an activity (running, coding, cooking) or a vivid scene. Never cut away from: the first two seconds, a punchline or emotional moment where the face sells it, abstract ideas with nothing to show, or the speaker describing themself.

For each cutaway give the word range it covers (from/to are word ids, inclusive, 1.5-4 seconds long), a short English stock-footage search query of 2-5 words describing the shot, and its subject: the one or two English nouns the shot must show (for "sunny beach waves", "beach"). Write query and subject in English even when the speech is in Hindi, Telugu or a mix. At most one cutaway per 8 seconds. It is right to return no cutaways for a clip that is about the person."""

EXAMPLE = '{"clips":[{"index":0,"cutaways":[{"from":12,"to":18,"query":"busy city street night","subject":"city street","why":"names the city"}]}]}'


@dataclass(frozen=True)
class Cutaway:
    start: float
    end: float
    query: str
    # The nouns a shot must show; the rest of the query is nice to have.
    subject: str = ""


@dataclass
class ClipWords:
    """A clip's words in source seconds, and the body spans they play in."""

    words: list[dict[str, Any]]
    spans: list[tuple[float, float]]


def prompt(clips: list[ClipWords]) -> str:
    blocks = []
    for index, clip in enumerate(clips):
        body_start = clip.spans[0][0] if clip.spans else 0.0
        lines = " ".join(
            f"{i}:{w['word']}" + (f"@{w['start'] - body_start:.1f}s" if i % 10 == 0 else "")
            for i, w in enumerate(clip.words[:MAX_WORDS_PER_CLIP])
        )
        blocks.append(f"[{index}] {lines}")
    return (
        "Each clip is its index, then its words as id:word (every tenth word shows seconds from the clip start).\n\n"
        + "\n\n".join(blocks)
        + f"\n\nReturn JSON only, like: {EXAMPLE}"
    )


async def plan_cutaways(clips: list[ClipWords], client: Any) -> list[list[Cutaway]]:
    """Validated cutaways per clip, in the order given; an unusable answer gives none."""
    if not clips:
        return []
    response = await client.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt(clips)}],
        temperature=0.3, max_tokens=250 * len(clips) + 200, json_mode=True,
    )
    try:
        data = json.loads(response[response.find("{"): response.rfind("}") + 1])
    except (ValueError, TypeError) as exc:
        log.warning("B-roll planner returned unreadable JSON: %s", exc)
        return [[] for _ in clips]
    raw_by_index = {
        item.get("index"): item.get("cutaways") or []
        for item in data.get("clips", []) if isinstance(item, dict)
    }
    return [validate(raw_by_index.get(index, []), clip) for index, clip in enumerate(clips)]


def validate(raw: list[Any], clip: ClipWords) -> list[Cutaway]:
    """Turn the model's word ranges into cutaways that obey the editing rules."""
    words = clip.words
    if not words or not clip.spans:
        return []
    body = sum(end - start for start, end in clip.spans)
    budget = body * MAX_COVERAGE
    kept: list[Cutaway] = []
    for item in sorted((r for r in raw if isinstance(r, dict)), key=lambda r: _int(r.get("from"))):
        first, last, query = _int(item.get("from")), _int(item.get("to")), str(item.get("query") or "").strip()
        if not query or not (0 <= first <= last < len(words)):
            continue
        start = float(words[first]["start"])
        end = min(max(float(words[last]["end"]), start + MIN_CUTAWAY_SECONDS), start + MAX_CUTAWAY_SECONDS)
        span = next(((a, b) for a, b in clip.spans if a <= start < b), None)
        if span is None:
            continue
        end = min(end, span[1])
        if end - start < MIN_CUTAWAY_SECONDS or _elapsed(start, clip.spans) < NO_CUTAWAY_BEFORE_SECONDS:
            continue
        if kept and start - kept[-1].end < MIN_GAP_SECONDS:
            continue
        if budget - (end - start) < 0:
            break
        budget -= end - start
        subject = str(item.get("subject") or "").strip()[:60]
        kept.append(Cutaway(round(start, 3), round(end, 3), query[:80], subject))
    return kept


def _elapsed(t: float, spans: list[tuple[float, float]]) -> float:
    """Seconds of the body played before source time ``t``."""
    total = 0.0
    for start, end in spans:
        if t < end:
            return total + max(0.0, t - start)
        total += end - start
    return total


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
