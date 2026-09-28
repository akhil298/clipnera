"""Following a creator's script, when they give one.

A pasted script can be what they say on camera, a voiceover to read, text for
the screen, or loose notes. ``resolve_mode`` decides which from how much of it
was actually spoken, unless the creator chose. In spoken mode ``align`` finds
the best take of every line; the director may not reorder or drop them.
Matching is plain text comparison, so following a script costs no AI call.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from edit_engine.story import normalize, similarity

ScriptMode = Literal["auto", "spoken", "voiceover", "onscreen", "direction"]
SCRIPT_MODES: tuple[str, ...] = ("auto", "spoken", "voiceover", "onscreen", "direction")

# A line counts as said when a take matches it at least this well.
LINE_MATCH = 0.55
# Takes within this score of the best are equally good; the later one wins.
TAKE_TIE = 0.05
# Consecutive sentences a single script line may span.
MAX_SPAN = 3
SPOKEN_COVERAGE = 0.25


def script_lines(script: str) -> list[str]:
    """Script sentences, split at sentence ends and line breaks."""
    pieces = re.split(r"(?<=[.!?।॥])\s+|\n+", script.strip())
    return [" ".join(p.split()) for p in pieces if normalize(p)]


def align(lines: list[str], sentences: list[dict[str, Any]], dropped: set[str] | None = None) -> list[dict[str, Any]]:
    """For each script line, its best take as a run of 1-3 consecutive sentence IDs, or none.

    Takes are searched across every file; among near-equal matches the later
    take wins, because creators re-record a line until they are happy.
    """
    dropped = dropped or set()
    candidates: list[tuple[list[str], str]] = []
    for i in range(len(sentences)):
        ids, text = [], []
        for sentence in sentences[i:i + MAX_SPAN]:
            if sentence["src"] != sentences[i]["src"] or sentence["id"] in dropped:
                break
            ids.append(sentence["id"])
            text.append(sentence["text"])
            candidates.append((list(ids), " ".join(text)))
    result = []
    for line in lines:
        scored = [(similarity(line, text), index, ids) for index, (ids, text) in enumerate(candidates)]
        best = max((s for s, _, _ in scored), default=0.0)
        if best < LINE_MATCH:
            result.append({"text": line, "sentences": [], "score": round(best, 3)})
            continue
        ties = [(index, ids) for score, index, ids in scored if score >= best - TAKE_TIE]
        _, ids = max(ties, key=lambda t: t[0])
        result.append({"text": line, "sentences": ids, "score": round(best, 3)})
    return result


def coverage(aligned: list[dict[str, Any]]) -> float:
    return sum(1 for line in aligned if line["sentences"]) / len(aligned) if aligned else 0.0


def resolve_mode(requested: str, has_script: bool, has_speech: bool, spoken_coverage: float) -> str:
    """The script's role for this reel: ``none`` when there is no script."""
    if not has_script:
        return "none"
    if requested != "auto":
        return requested
    if not has_speech:
        return "voiceover"
    return "spoken" if spoken_coverage >= SPOKEN_COVERAGE else "direction"


def unscripted(aligned: list[dict[str, Any]], sentences: list[dict[str, Any]], dropped: set[str]) -> list[str]:
    """Sentence IDs said on camera that no script line uses (off-script speech)."""
    used = {i for line in aligned for i in line["sentences"]}
    return [s["id"] for s in sentences if s["id"] not in used and s["id"] not in dropped]
