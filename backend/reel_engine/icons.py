"""Icons that mean what was said, or none.

Word matching alone picks a dinner plate for "weight plates" and a kangaroo for "jump rope". Here word matching
only proposes candidates from the kit; one text call sees each phrase in its context with its candidates and picks
the icon that literally depicts the thing, or none. A wrong icon is worse than no icon.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

import json
from functools import lru_cache
from pathlib import Path

from beats import kit
from core.logging_config import get_logger
from reel_engine.plan import AssetRef

log = get_logger(__name__)

CANDIDATES = 8
EMOJI_DIR = Path(__file__).resolve().parents[1] / "static" / "motion" / "emoji"
KINDS = ("object3d", "icon_line")
# Requests for decoration rather than meaning get no icon.
DECORATIVE = {"sparkles", "sparkle", "star", "stars", "fire", "magic"}


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Choice(_M):
    request: int
    icon: str
    why: str


class Choices(_M):
    choices: list[Choice]


SYSTEM = """You choose icons for a video's on-screen labels. Each request is a thing named in the video, the words
around it, and candidate icons (id: what the icon shows). Pick the candidate that LITERALLY shows that thing as it
is meant here - "weight plates" in a gym are not dinner plates, "battle ropes" are not a knot, a "pull-up bar" is
not signal bars, "CapCut" is an app, not a cap. The thing must be meant literally: a word inside a figure of
speech names nothing to show - "in your head" is not a brain, "the key is" is not a key, "the heart of it" is not a
heart, "on the table" is not a table, "I'm buying a car" as an example of a choice is not a car being shown. If no
candidate shows it, or the word is used figuratively, answer "none". Never pick a loose, metaphorical or decorative
match. Animated emoji (ids starting e_) are fine when the emoji literally shows the
thing or the feeling said; prefer them for feelings and simple objects. JSON only."""


def candidates(query: str, n: int = CANDIDATES, kinds: tuple[str, ...] = KINDS) -> list[dict]:
    """Kit icons whose trigger words overlap the query's, best first."""
    asked = kit.words_of(query)
    if not asked:
        return []
    scored = []
    for entry in kit.manifest():
        if entry.get("kind") not in kinds:
            continue
        triggers = {w.lower() for w in entry.get("words") or []}
        hits = asked & triggers
        if hits and kit.path_of(entry):
            scored.append((len(hits) * 2 + (entry.get("kind") == "object3d"), entry))
    scored.sort(key=lambda s: -s[0])
    return [e for _, e in scored[:n]]


@lru_cache(maxsize=1)
def emoji_library() -> list[dict]:
    """Animated emoji (scripts/build_asset_libraries.py) as candidate entries, or none when the library is not fetched."""
    path = EMOJI_DIR / "manifest.json"
    if not path.exists():
        return []
    entries = json.loads(path.read_text()).get("entries", {})
    return [{"id": key, "kind": "emoji", "words": e["words"], "path": str(EMOJI_DIR / e["file"]), "licence": e["licence"],
             "source": e["source"], "popularity": e.get("popularity", 0)} for key, e in entries.items() if (EMOJI_DIR / e["file"]).exists()]


def emoji_candidates(query: str, n: int = 4) -> list[dict]:
    asked = kit.words_of(query)
    hits = [(len(asked & set(e["words"])), e["popularity"], e) for e in emoji_library() if asked & set(e["words"])]
    return [e for *_, e in sorted(hits, key=lambda h: (-h[0], -h[1]))[:n]]


def label(entry: dict) -> str:
    return f"{entry['id']}: {', '.join((entry.get('words') or [])[:6])}"


async def choose(requests: list[tuple[str, str]], animated: frozenset[int] = frozenset(),
                 kinds: tuple[str, ...] = KINDS, n: int = CANDIDATES) -> list[AssetRef | None]:
    """For each (query, context), the kit icon that truly shows it, or None, from ``n`` candidates each. Requests
    numbered in ``animated`` (caption lines) may also get an animated emoji."""
    from reel_engine.ai import vision_json

    pools = [[] if not q or kit.words_of(q) <= DECORATIVE else candidates(q, n, kinds=kinds) + (emoji_candidates(q) if k in animated else [])
             for k, (q, _) in enumerate(requests)]
    asked = [(n, q, ctx, pool) for n, ((q, ctx), pool) in enumerate(zip(requests, pools)) if pool]
    result: list[AssetRef | None] = [None] * len(requests)
    if not asked:
        return result
    lines = [f"request {n}: '{q}' - said: \"{ctx[:120]}\"\n  candidates: " + " | ".join(label(e) for e in pool) for n, q, ctx, pool in asked]
    try:
        answer = await vision_json(SYSTEM, "\n".join(lines) + "\n\nChoose. JSON only.", [], Choices, max_tokens=2000,
                                   step="reel_icons")
    except Exception as exc:  # without the check no icon is shown, rather than a guessed one
        log.warning("Icon choice failed, labels go without icons: %s", exc)
        return result
    by_request = {c.request: c.icon for c in answer.choices}
    for n, _, _, pool in asked:
        entry = next((e for e in pool if e["id"] == by_request.get(n)), None)
        if entry:
            path = entry["path"] if entry.get("kind") == "emoji" else str(kit.path_of(entry))
            result[n] = AssetRef(id=entry["id"], kind="icon", path=path, licence=entry.get("licence", ""), source=entry.get("source", "kit"))
    log.info("Icons: %d of %d requests got one", sum(1 for r in result if r), len(requests))
    return result
