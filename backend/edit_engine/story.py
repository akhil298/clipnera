"""The spoken content of the footage: sentences, retakes and what kind of video it is.

Everything here is plain code on word timings; no model is called. Sentences
get short IDs (``s0``, ``s1``...) that the director answers in, and the
compiler turns back into word-exact times.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from transcription.language import SENTENCE_TERMINALS, is_hesitation

# A pause this long ends a sentence even without punctuation.
SENTENCE_PAUSE = 0.8
MAX_SENTENCE_WORDS = 30
# Two sentences this similar, this close together, are takes of one line.
RETAKE_SIMILARITY = 0.6
RETAKE_WINDOW_SECONDS = 25.0
RETAKE_LOOKAHEAD = 3
# A later take shorter than this share of the longest take is a fragment, not the keeper.
RETAKE_FRAGMENT = 0.6
RESTART_PHRASES = (
    "let me start again", "let me start over", "start again", "one more time", "take two", "let me redo",
    "let me try that again", "sorry let me", "wait let me", "cut that", "okay again", "from the top",
)

CONTENT_TYPES = ("talking_head", "montage", "vlog")


def normalize(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower())


def similarity(a: str, b: str) -> float:
    left, right = normalize(a), normalize(b)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def sentences_from_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sentences per source file, split at punctuation, long pauses and a word cap.

    ``words`` carry ``src`` (source index), ``start``, ``end`` and ``word`` in
    source time. Each sentence keeps the index range of its words.
    """
    sentences: list[dict[str, Any]] = []
    first = 0

    def close(last: int) -> None:
        if last < first:
            return
        span = words[first:last + 1]
        sentences.append({
            "id": f"s{len(sentences)}", "src": span[0]["src"], "start": float(span[0]["start"]),
            "end": float(span[-1]["end"]), "text": " ".join(str(w["word"]).strip() for w in span).strip(),
            "w0": first, "w1": last,
        })

    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else None
        ends = (
            following is None
            or following["src"] != word["src"]
            or str(word["word"]).strip().endswith(SENTENCE_TERMINALS)
            or float(following["start"]) - float(word["end"]) >= SENTENCE_PAUSE
            or index - first + 1 >= MAX_SENTENCE_WORDS
        )
        if ends:
            close(index)
            first = index + 1
    return sentences


def is_restart(text: str) -> bool:
    lowered = " ".join(normalize(text))
    return any(phrase in lowered for phrase in RESTART_PHRASES)


def retake_groups(sentences: list[dict[str, Any]]) -> list[list[str]]:
    """Groups of sentence IDs that are takes of the same line, in recording order."""
    parent = {s["id"]: s["id"] for s in sentences}

    def root(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for i, sentence in enumerate(sentences):
        # Takes may sit in different files: creators often re-record a line as a new clip.
        for other in sentences[i + 1:i + 1 + RETAKE_LOOKAHEAD]:
            if other["src"] == sentence["src"] and other["start"] - sentence["end"] > RETAKE_WINDOW_SECONDS:
                break
            if _same_line(sentence["text"], other["text"]):
                parent[root(other["id"])] = root(sentence["id"])
    groups: dict[str, list[str]] = {}
    for sentence in sentences:
        groups.setdefault(root(sentence["id"]), []).append(sentence["id"])
    return [ids for ids in groups.values() if len(ids) > 1]


def _same_line(a: str, b: str) -> bool:
    left, right = normalize(a), normalize(b)
    if len(left) < 3 or len(right) < 3:
        return False
    if similarity(a, b) >= RETAKE_SIMILARITY:
        return True
    # A false start: the earlier take is the opening of the later one.
    head = min(len(left), len(right), 5)
    return left[:head] == right[:head] and head >= 4


def best_take(group: list[str], by_id: dict[str, dict[str, Any]]) -> str:
    """The last complete take: the latest one that is not a fragment of the longest."""
    longest = max(len(normalize(by_id[i]["text"])) for i in group)
    complete = [i for i in group if len(normalize(by_id[i]["text"])) >= RETAKE_FRAGMENT * longest]
    return complete[-1] if complete else group[-1]


def dropped_takes(sentences: list[dict[str, Any]], groups: list[list[str]]) -> set[str]:
    """Sentence IDs to leave out by default: losing takes and "let me start again" lines."""
    by_id = {s["id"]: s for s in sentences}
    dropped = {i for group in groups for i in group if i != best_take(group, by_id)}
    dropped.update(s["id"] for s in sentences if is_restart(s["text"]))
    dropped.update(s["id"] for s in sentences if all(is_hesitation(w) for w in s["text"].split()))
    return dropped


def classify(speech_seconds: float, raw_seconds: float, shots: list[dict[str, Any]], has_voiceover: bool) -> str:
    """talking_head, montage or vlog, from how much is spoken and how often a face is on screen."""
    if raw_seconds <= 0:
        return "montage"
    speech_ratio = speech_seconds / raw_seconds
    if has_voiceover or speech_ratio < 0.2:
        return "montage"
    face_share = sum(s["end"] - s["start"] for s in shots if s.get("faces")) / max(1.0, sum(s["end"] - s["start"] for s in shots))
    if speech_ratio >= 0.55 and face_share >= 0.6:
        return "talking_head"
    return "vlog"
