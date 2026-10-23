"""Icons that mean what was said, or none.

Word matching alone picks a dinner plate for "weight plates" and a kangaroo for "jump rope". Here word matching
only proposes candidates from the kit; one text call sees each phrase in its context with its candidates and picks
the icon that literally depicts the thing, or none. A wrong icon is worse than no icon.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from beats import kit
from core.logging_config import get_logger
from reel_engine.plan import AssetRef

log = get_logger(__name__)

CANDIDATES = 8
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
not signal bars, "CapCut" is an app, not a cap. If no candidate shows it, answer "none". Never pick a loose,
metaphorical or decorative match. JSON only."""


def candidates(query: str, n: int = CANDIDATES) -> list[dict]:
    """Kit icons whose trigger words overlap the query's, best first."""
    asked = kit.words_of(query)
    if not asked:
        return []
    scored = []
    for entry in kit.manifest():
        if entry.get("kind") not in KINDS:
            continue
        triggers = {w.lower() for w in entry.get("words") or []}
        hits = asked & triggers
        if hits and kit.path_of(entry):
            scored.append((len(hits) * 2 + (entry.get("kind") == "object3d"), entry))
    scored.sort(key=lambda s: -s[0])
    return [e for _, e in scored[:n]]


def label(entry: dict) -> str:
    return f"{entry['id']}: {', '.join((entry.get('words') or [])[:6])}"


async def choose(requests: list[tuple[str, str]]) -> list[AssetRef | None]:
    """For each (query, context), the kit icon that truly shows it, or None."""
    from clients.ai import get_text_client

    pools = [[] if not q or kit.words_of(q) <= DECORATIVE else candidates(q) for q, _ in requests]
    asked = [(n, q, ctx, pool) for n, ((q, ctx), pool) in enumerate(zip(requests, pools)) if pool]
    result: list[AssetRef | None] = [None] * len(requests)
    if not asked:
        return result
    lines = [f"request {n}: '{q}' - said: \"{ctx[:120]}\"\n  candidates: " + " | ".join(label(e) for e in pool) for n, q, ctx, pool in asked]
    try:
        client = get_text_client(is_pro=True, step="beat_planning")
        answer = await client.chat_json([{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": "\n".join(lines) + "\n\nChoose. JSON only."}], Choices, max_tokens=2000)
    except Exception as exc:  # without the check no icon is shown, rather than a guessed one
        log.warning("Icon choice failed, labels go without icons: %s", exc)
        return result
    by_request = {c.request: c.icon for c in answer.choices}
    for n, _, _, pool in asked:
        entry = next((e for e in pool if e["id"] == by_request.get(n)), None)
        if entry:
            result[n] = AssetRef(id=entry["id"], kind="icon", path=str(kit.path_of(entry)), licence=entry.get("licence", ""),
                                 source=entry.get("source", "kit"))
    log.info("Icons: %d of %d requests got one", sum(1 for r in result if r), len(requests))
    return result
