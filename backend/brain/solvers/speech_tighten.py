"""speech.tighten: cut pauses and filler words out of speech, never inside a word (BLUEPRINT §3B.3.5).

Gaps longer than the style allows are closed, filler words the analysis is sure about are
dropped, and every kept word keeps a short pad before and after so speech doesn't sound
clipped. Returns the ranges of the source to keep.
"""

from __future__ import annotations

from collections.abc import Sequence

from understanding.mud import Word

GAP_SECONDS = {"natural": 0.8, "tight": 0.5, "punchy": 0.35}
FILLER_CONFIDENCE = 0.7
# Assumed confidence when the transcriber gave none.
DEFAULT_CONFIDENCE = 0.8
PAD_BEFORE = 0.09
PAD_AFTER = 0.06
# A kept piece shorter than this flickers past as its own shot; it joins its neighbour instead,
# keeping the pause between them.
MIN_PIECE_SECONDS = 1.2


def keep_ranges(words: Sequence[Word], t0: float, t1: float, style: str = "natural") -> list[tuple[float, float]]:
    """Source ranges in [t0, t1] to keep. A range never starts or ends inside a kept word."""
    if style not in GAP_SECONDS:
        return [(t0, t1)]
    gap = GAP_SECONDS[style]
    inside = [(n, w) for n, w in enumerate(words) if w.t0 >= t0 - 1e-6 and w.t1 <= t1 + 1e-6]
    kept = [(n, w) for n, w in inside if not _drop(w)]
    if not kept:
        return [(t0, t1)]
    ranges: list[list[float]] = []
    for n, word in kept:
        # The pads stop at the neighbouring words, the cut ones too: an edge never lands inside a word.
        start = max(t0, word.t0 - PAD_BEFORE, words[n - 1].t1 if n > 0 else t0)
        end = min(t1, word.t1 + PAD_AFTER, words[n + 1].t0 if n + 1 < len(words) else t1)
        if ranges and word.t0 - (ranges[-1][1] - PAD_AFTER) <= gap:
            ranges[-1][1] = end
        else:
            if ranges:
                # Pads never reach into a neighbour.
                start = max(start, ranges[-1][1])
            ranges.append([start, end])
    return [(round(a, 3), round(b, 3)) for a, b in _join_short(ranges) if b - a > 0.05]


def _join_short(ranges: list[list[float]]) -> list[list[float]]:
    """Each piece under MIN_PIECE_SECONDS merged into the nearer of its neighbours."""
    joined = [list(r) for r in ranges]
    n = 0
    while len(joined) > 1 and n < len(joined):
        a, b = joined[n]
        if b - a >= MIN_PIECE_SECONDS:
            n += 1
            continue
        before = a - joined[n - 1][1] if n > 0 else float("inf")
        after = joined[n + 1][0] - b if n + 1 < len(joined) else float("inf")
        if before <= after:
            joined[n - 1][1] = b
            del joined[n]
        else:
            joined[n + 1][0] = a
            del joined[n]
    return joined


def _drop(word: Word) -> bool:
    conf = word.conf if word.conf is not None else DEFAULT_CONFIDENCE
    return word.filler is not None and conf >= FILLER_CONFIDENCE


def cuts_inside_words(ranges: Sequence[tuple[float, float]], words: Sequence[Word]) -> list[Word]:
    """Words a range edge falls strictly inside (the check §3B rule CT-06 runs)."""
    edges = [t for r in ranges for t in r]
    return [w for w in words if any(w.t0 + 1e-3 < t < w.t1 - 1e-3 for t in edges)]
