"""Which timeline item a phrase means: "the title", "the second clip", "it" (BLUEPRINT §3.9.7).

Deterministic and cheap: every item is scored on a few signals and the clear winner is
taken. When there is no clear winner the caller gets choices to show as chips; when
nothing of that kind exists, a question to ask.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from editor.timeline import ClipItem, GraphicItem, Item, MusicItem, SfxItem, TextItem, Timeline, Track

# Signal weights (TODO 5.3.2).
SELECTED = 3.0
UNDER_PLAYHEAD = 2.0
KIND_MATCH = 2.5
ORDINAL = 2.0
TEXT_MATCH = 1.5
RECENT = 1.2
# A winner needs this score, and this lead over the runner-up.
MIN_SCORE = 4.0
MIN_LEAD = 1.5
MAX_CHOICES = 4

Kind = str  # clip | title | music | sfx | effect

_KIND_WORDS: dict[Kind, tuple[str, ...]] = {
    "clip": ("clip", "clips", "shot", "shots", "video", "footage", "scene"),
    "title": ("title", "titles", "text", "caption", "heading", "headline", "words", "subtitle"),
    "music": ("music", "song", "track", "soundtrack", "audio", "beat"),
    "sfx": ("sound", "sfx", "whoosh", "effect sound", "swoosh"),
    "effect": ("sticker", "graphic", "effect", "overlay", "emoji"),
}
_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3,
             "fifth": 4, "5th": 4, "last": -1, "final": -1}
_STOP = {"the", "a", "an", "my", "this", "that", "of", "on", "in", "to", "make", "it", "and", "with"}


@dataclass(frozen=True)
class Entity:
    id: str
    kind: Kind
    track: str
    at: int
    end: int
    label: str
    # Words to match a quoted or named phrase against (text, asset name).
    words: frozenset[str] = field(default_factory=frozenset)


@dataclass
class Resolution:
    phrase: str
    entity: Entity | None = None
    choices: list[Entity] = field(default_factory=list)
    question: str | None = None


def entities(timeline: Timeline) -> list[Entity]:
    """Every item as something a phrase can point at, in timeline order."""
    found = []
    for track in timeline.tracks:
        for item in track.items:
            kind, label, words = _kind_label(timeline, track, item)
            found.append(Entity(item.id, kind, track.id, item.at, item.end, label, frozenset(words)))
    return sorted(found, key=lambda e: (e.at, e.track))


def _kind_label(timeline: Timeline, track: Track, item: Item) -> tuple[Kind, str, set[str]]:
    if isinstance(item, TextItem):
        return "title", f'"{item.text[:30]}"', _words(item.text)
    if isinstance(item, MusicItem):
        return "music", f"music {item.track}", _words(item.track)
    if isinstance(item, SfxItem):
        return "sfx", f"sound {item.name}", _words(item.name)
    if isinstance(item, GraphicItem):
        return "effect", f"graphic {item.id}", set()
    asset = timeline.assets.get(item.asset) if isinstance(item, ClipItem) else None
    name = Path(asset.key).stem if asset else item.id
    if track.kind == "audio":
        return "music", f"audio {name}", _words(name)
    return "clip", f"clip {name} at {item.at / timeline.fps:.1f}s", _words(name)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[\w']+", text.lower()) if w not in _STOP}


def phrase_kind(phrase: str, hint: str | None = None) -> Kind | None:
    """The kind of thing a phrase names, from its words, else the router's hint."""
    lowered = phrase.lower()
    for kind, words in _KIND_WORDS.items():
        if any(re.search(rf"\b{re.escape(w)}\b", lowered) for w in words):
            return kind
    return {"clip": "clip", "title": "title", "caption": "title", "music": "music", "effect": "effect"}.get(hint or "")


def resolve(phrase: str, timeline: Timeline, *, selection: Sequence[str], playhead: int,
            recent: Iterable[str] = (), hint: str | None = None) -> Resolution:
    """Resolve one phrase. ``recent`` lists item ids changed lately, newest first."""
    pool = entities(timeline)
    kind = phrase_kind(phrase, hint)
    lowered = phrase.lower()
    if kind and not any(e.kind == kind for e in pool):
        return Resolution(phrase, question=f"There's no {kind} in the project yet. Which one did you mean?")

    recent_ids = list(dict.fromkeys(recent))
    ordinal = next((index for word, index in _ORDINALS.items() if re.search(rf"\b{word}\b", lowered)), None)
    named = _words(re.sub(r"[\"'“”‘’]", " ", phrase)) - set().union(*_KIND_WORDS.values()) - set(_ORDINALS)
    of_kind = [e for e in pool if e.kind == kind] if kind else pool

    scored: list[tuple[float, Entity]] = []
    for entity in pool:
        score = 0.0
        at_ordinal = ordinal is not None and entity in of_kind and of_kind.index(entity) == (ordinal % len(of_kind))
        # "the second clip" names its position: where the playhead is or what changed last doesn't argue with it.
        loose = ordinal is None or at_ordinal
        if entity.id in selection:
            score += SELECTED
        if loose and entity.at <= playhead < entity.end:
            score += UNDER_PLAYHEAD
        if kind and entity.kind == kind:
            score += KIND_MATCH
        if at_ordinal:
            score += ORDINAL
        elif kind and of_kind == [entity]:
            score += ORDINAL  # "the title" when there is only one: as certain as naming its position.
        if named and named & entity.words:
            score += TEXT_MATCH * len(named & entity.words) / len(named)
        if loose and entity.id in recent_ids[:3]:
            score += RECENT
        if kind and entity.kind != kind:
            score = min(score, MIN_SCORE - MIN_LEAD)  # The wrong kind never wins.
        scored.append((score, entity))

    ranked = sorted(scored, key=lambda pair: (-pair[0], pair[1].at))
    if not ranked or ranked[0][0] <= 0:
        return Resolution(phrase, question=f'Which item do you mean by "{phrase}"?')
    top, runner_up = ranked[0][0], ranked[1][0] if len(ranked) > 1 else 0.0
    if top >= MIN_SCORE and top - runner_up >= MIN_LEAD:
        return Resolution(phrase, entity=ranked[0][1])
    choices = [entity for score, entity in ranked if score > 0 and (not kind or entity.kind == kind)][:MAX_CHOICES]
    if not choices:
        return Resolution(phrase, question=f'Which item do you mean by "{phrase}"?')
    return Resolution(phrase, choices=choices)
