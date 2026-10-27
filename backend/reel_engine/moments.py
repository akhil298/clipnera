"""Moments: the self-contained ideas in a long video, ranked, so each reel is cut from the best of them.

One text call (the strong model: choosing what is worth a reel decides the score more than any effect) reads the
transcript sentence by sentence and returns the moments that would stand alone as a reel: where each starts and
ends, the line that hooks hardest, the line that pays it off, an on-screen hook headline, and scores for hook,
payoff and standing alone. The editor then works on one moment at a time with a close look at just
that stretch, instead of judging a whole hour from a few dozen frames, and a video with several strong moments
gives several reels.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from core.logging_config import get_logger
from reel_engine.director import sentences
from reel_engine.plan import Word

log = get_logger(__name__)

MIN_SECONDS, MAX_SECONDS = 25.0, 95.0
GOOD_ENOUGH = 4.5       # more lenient - take decent moments too
PAD = 0.2
SPEECH_PER_REEL = 75.0  # more reels per minute of speech without shrinking them artificially


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Moment(_M):
    start: int          # first sentence id
    end: int            # last sentence id
    hook: int           # the sentence that hooks hardest (may be anywhere inside)
    payoff: int         # the sentence that pays it off
    title: str
    headline: str       # the hook as on-screen text: a specific question or claim from the moment, 3-7 words
    hook_score: float
    payoff_score: float
    standalone_score: float
    why: str


class Moments(_M):
    moments: list[Moment]


SYSTEM = """You find the moments in a long video that would each make a great short reel on their own. Read the
transcript (sentences with ids and times). A moment is a stretch of consecutive sentences, 25-90 seconds, that
makes ONE complete point: a strong opening, a reason to keep watching, and a payoff (an answer, a twist, a lesson,
a punchline). Never stitch unrelated parts. Prefer moments a stranger understands without the rest of the video.
Start each moment on a complete sentence that makes sense cold - never on "and", "so", "because" or a reply to a
question the viewer did not hear; leave out the warm-up, small talk and lines that repeat a point already made.
For each: start and end sentence ids, hook = the single sentence that would stop a scroller (it may sit inside the
moment and be moved to the front), payoff = the sentence that lands it, title (2-6 words), headline = the hook as
on-screen text, 3-7 words, a specific question or bold claim this moment answers, in the speaker's language and
script as spoken (romanized Hindi stays romanized, e.g. "Athletes body hair kyun hatate hain?"), never one generic
word like "ENERGY" or "HAIR"; scores 0-10 for hook, payoff and standalone (be strict: 9+ only for a moment that
would go viral), and why in one line. Return the best moments first, as many distinct topics as the video truly
has (up to 25), never overlapping, never two on the same point. If nothing stands alone, return the single best
stretch. JSON only."""


def listing(words: list[Word]) -> tuple[str, list[tuple[int, int]]]:
    spans = sentences(words)
    rows = [f"s{n} [{words[a].t0:.0f}-{words[b].t1:.0f}s] " + " ".join(w.text for w in words[a:b + 1])
            for n, (a, b) in enumerate(spans)]
    return "\n".join(rows), spans


def score(m: Moment) -> float:
    return round((m.hook_score + m.payoff_score + m.standalone_score) / 3, 2)


async def find(words: list[Word], brief: str = "") -> list[tuple[Moment, float, float, int]]:
    """Ranked moments as (moment, start second, end second, source index), best first; [] when there is no speech."""
    from reel_engine.ai import vision_json

    if len(words) < 30:
        return []
    text, spans = listing(words)
    try:
        found = await vision_json(SYSTEM, f"User brief: {brief or '(none)'}\n\nTranscript:\n{text}\n\nJSON only.", [], Moments,
                                  max_tokens=4000, step="reel_moments")
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
        src = words[a].src
        if t1 - t0 < MIN_SECONDS or t1 - t0 > MAX_SECONDS * 1.3 or any(s == src and t0 < z and y < t1 for y, z, s in taken):
            continue
        taken.append((t0, t1, src))
        out.append((m, t0, t1, src))
    log.info("Moments: %s", ", ".join(f"{m.title} {score(m)} [{t0:.0f}-{t1:.0f}s]" for m, t0, t1, _ in out) or "none")
    return out


def reels_for(words: list[Word], cap: int) -> int:
    """How many reels the footage can give: one per SPEECH_PER_REEL seconds of speech, at least one, at most ``cap``."""
    speech = sum(w.t1 - w.t0 for w in words if not w.filler)
    return max(1, min(cap, math.ceil(speech / SPEECH_PER_REEL)))


def worth_a_reel(found: list[tuple[Moment, float, float, int]], most: int) -> list[tuple[Moment, float, float, int]]:
    """The moments that each deserve their own reel (the best one always), up to ``most``."""
    if not found:
        return []
    # Take more moments - be generous
    out = [found[0]]
    for f in found[1:]:
        if len(out) >= most:
            break
        if score(f[0]) >= 4.0:
            out.append(f)
    return out


def dump(found: list[tuple[Moment, float, float, int]]) -> list:
    """Moments as JSON (kept on the edit, so a resumed job makes the same reels)."""
    return [[m.model_dump(), t0, t1, src] for m, t0, t1, src in found]


def load(saved: list) -> list[tuple[Moment, float, float, int]]:
    return [(Moment(**m), float(t0), float(t1), int(src)) for m, t0, t1, src in saved]
