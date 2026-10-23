"""Moments: the self-contained ideas in a long video, ranked, so each reel is cut from the best of them.

One text call (the plan's light model) reads the transcript sentence by sentence and returns the moments that would
stand alone as a reel: where each starts and ends, the line that hooks hardest, the line that pays it off, and
scores for hook, payoff and standing alone. The editor then works on one moment at a time with a close look at just
that stretch, instead of judging a whole hour from a few dozen frames, and a video with several strong moments
gives several reels.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from core.logging_config import get_logger
from reel_engine.director import sentences
from reel_engine.plan import Word

log = get_logger(__name__)

MIN_SECONDS, MAX_SECONDS = 18.0, 75.0
GOOD_ENOUGH = 7.0       # a moment worth its own reel scores at least this (average of the three scores)
PAD = 0.3


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Moment(_M):
    start: int          # first sentence id
    end: int            # last sentence id
    hook: int           # the sentence that hooks hardest (may be anywhere inside)
    payoff: int         # the sentence that pays it off
    title: str
    hook_score: float
    payoff_score: float
    standalone_score: float
    why: str


class Moments(_M):
    moments: list[Moment]


SYSTEM = """You find the moments in a long video that would each make a great short reel on their own. Read the
transcript (sentences with ids and times). A moment is a stretch of consecutive sentences, 20-70 seconds, that
makes ONE complete point: a strong opening, a reason to keep watching, and a payoff (an answer, a twist, a lesson,
a punchline). Never stitch unrelated parts. Prefer moments a stranger understands without the rest of the video.
For each: start and end sentence ids, hook = the single sentence that would stop a scroller (it may sit inside the
moment and be moved to the front), payoff = the sentence that lands it, title (2-6 words), scores 0-10 for hook,
payoff and standalone (be strict: 9+ only for a moment that would go viral), and why in one line. Return the best
moments first, at most 8, never overlapping. If nothing stands alone, return the single best stretch. JSON only."""


def listing(words: list[Word]) -> tuple[str, list[tuple[int, int]]]:
    spans = sentences(words)
    rows = [f"s{n} [{words[a].t0:.0f}-{words[b].t1:.0f}s] " + " ".join(w.text for w in words[a:b + 1])
            for n, (a, b) in enumerate(spans)]
    return "\n".join(rows), spans


def score(m: Moment) -> float:
    return round((m.hook_score + m.payoff_score + m.standalone_score) / 3, 2)


async def find(words: list[Word], brief: str = "") -> list[tuple[Moment, float, float, int]]:
    """Ranked moments as (moment, start second, end second, source index), best first; [] when there is no speech."""
    from clients.ai import get_text_client

    if len(words) < 30:
        return []
    text, spans = listing(words)
    client = get_text_client(is_pro=False, step="moment_finder")
    try:
        found = await client.chat_json([{"role": "system", "content": SYSTEM},
                                        {"role": "user", "content": f"User brief: {brief or '(none)'}\n\nTranscript:\n{text}\n\nJSON only."}],
                                       Moments, max_tokens=4000)
    except Exception as exc:  # without moments the editor works on the whole video, as before
        log.warning("Moment finder failed: %s", exc)
        return []
    out, taken = [], []
    for m in sorted(found.moments, key=score, reverse=True):
        if not (0 <= m.start <= m.end < len(spans)):
            continue
        a, b = spans[m.start][0], spans[m.end][1]
        if words[a].src != words[b].src:
            continue
        t0, t1 = max(0.0, words[a].t0 - PAD), words[b].t1 + PAD
        if t1 - t0 < MIN_SECONDS or t1 - t0 > MAX_SECONDS * 1.3 or any(t0 < z and y < t1 for y, z, _ in taken):
            continue
        taken.append((t0, t1, words[a].src))
        out.append((m, t0, t1, words[a].src))
    log.info("Moments: %s", ", ".join(f"{m.title} {score(m)} [{t0:.0f}-{t1:.0f}s]" for m, t0, t1, _ in out) or "none")
    return out


def worth_a_reel(found: list[tuple[Moment, float, float, int]], most: int) -> list[tuple[Moment, float, float, int]]:
    """The moments that each deserve their own reel (the best one always), up to ``most``."""
    if not found:
        return []
    return [found[0]] + [f for f in found[1:] if score(f[0]) >= GOOD_ENOUGH][:max(0, most - 1)]
