"""caption.break: split speech into caption cues and lines (BLUEPRINT §3B.3.6).

subtitle_styling.ass_generator.group_words fills lines greedily for the burned-in captions;
this is the DP the brain checks and plans with. A cue costs more when it is ragged, ends on a
function word, reads faster than 17 characters a second, or lasts outside 0.7–6 s. Lines fit
22 characters on 9:16 and 42 on 16:9; word-by-word mode makes cues of 1–4 words.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from understanding.mud import Word

MAX_CPS = 17.0
MIN_SECONDS, MAX_SECONDS = 0.7, 6.0
CHARS_VERTICAL, CHARS_WIDE = 22, 42
MAX_LINES = 2
FUNCTION_WORDS = frozenset("a an the of to in on at for and or but with by from as is are was".split())


@dataclass(frozen=True)
class Cue:
    t0: float
    t1: float
    lines: tuple[str, ...]
    w0: int
    w1: int


def max_chars(width: int, height: int) -> int:
    return CHARS_VERTICAL if height > width else CHARS_WIDE


def break_cues(words: Sequence[Word], *, width: int, height: int, word_by_word: bool = False) -> list[Cue]:
    if not words:
        return []
    limit = max_chars(width, height)
    longest = 4 if word_by_word else 14
    n = len(words)
    best = [float("inf")] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0.0
    for end in range(1, n + 1):
        for start in range(max(0, end - longest), end):
            lines = _lines([w.text for w in words[start:end]], limit)
            if lines is None:
                continue
            cost = best[start] + _cost(words[start:end], lines, limit, word_by_word)
            if cost < best[end]:
                best[end], back[end] = cost, start
    cues: list[Cue] = []
    end = n
    while end > 0:
        start = back[end]
        lines = _lines([w.text for w in words[start:end]], limit) or (" ".join(w.text for w in words[start:end]),)
        cues.append(Cue(words[start].t0, words[end - 1].t1, lines, words[start].i, words[end - 1].i))
        end = start
    return cues[::-1]


def _lines(texts: list[str], limit: int) -> tuple[str, ...] | None:
    """The most even split of the words into at most two lines that fit, or None."""
    joined = " ".join(texts)
    if len(joined) <= limit:
        return (joined,)
    options = [(" ".join(texts[:k]), " ".join(texts[k:])) for k in range(1, len(texts))]
    fitting = [o for o in options if len(o[0]) <= limit and len(o[1]) <= limit]
    if not fitting or MAX_LINES < 2:
        return None
    return min(fitting, key=lambda o: abs(len(o[0]) - len(o[1])))


def _cost(words: Sequence[Word], lines: tuple[str, ...], limit: int, word_by_word: bool) -> float:
    seconds = max(0.01, words[-1].t1 - words[0].t0)
    chars = sum(len(line) for line in lines)
    cost = 1.0  # Per cue: fewer, fuller cues read better.
    if len(lines) == 2:
        cost += abs(len(lines[0]) - len(lines[1])) / limit
    if words[-1].text.lower().strip(".,!?") in FUNCTION_WORDS and not word_by_word:
        cost += 2.0
    if chars / seconds > MAX_CPS:
        cost += (chars / seconds - MAX_CPS) * 0.5
    if not word_by_word and seconds < MIN_SECONDS:
        cost += (MIN_SECONDS - seconds) * 4
    if seconds > MAX_SECONDS:
        cost += (seconds - MAX_SECONDS) * 4
    return cost
