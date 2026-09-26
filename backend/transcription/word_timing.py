"""Clean Whisper's word timings before captions and cuts use them.

Whisper's word boundaries are good but not tidy: a word before a pause often
"ends" at the start of the next word, so its caption lingers through the
silence and a jump cut keeps the dead air; neighbouring words can overlap; and
a word can come back with zero length. Captions are timed per word, so these
show directly as captions that lag or flash.
"""

from __future__ import annotations

from typing import Any

MIN_WORD_SECONDS = 0.06
# A spoken word rarely lasts longer than this plus a little per character;
# anything longer has absorbed the silence after it.
BASE_WORD_SECONDS = 0.5
SECONDS_PER_CHAR = 0.09
MAX_WORD_SECONDS = 1.6


def plausible_length(word: str) -> float:
    return min(MAX_WORD_SECONDS, BASE_WORD_SECONDS + SECONDS_PER_CHAR * len(word.strip()))


def clean_word_timings(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Words in order, not overlapping, at least a few frames long, none stretched over silence."""
    ordered = sorted(words, key=lambda w: (float(w["start"]), float(w["end"])))
    cleaned: list[dict[str, Any]] = []
    for word in ordered:
        start, end = float(word["start"]), float(word["end"])
        if cleaned and start < cleaned[-1]["end"]:
            # An overlap almost always means the earlier word was ended late.
            previous = cleaned[-1]
            previous["end"] = round(max(previous["start"] + MIN_WORD_SECONDS, start), 3)
            start = max(start, previous["end"])
        end = min(max(end, start + MIN_WORD_SECONDS), start + plausible_length(str(word.get("word", ""))))
        cleaned.append({**word, "start": round(start, 3), "end": round(end, 3)})
    return cleaned
