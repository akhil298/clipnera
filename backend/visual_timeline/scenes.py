"""Attaching the visual timeline to transcript sentences."""

from __future__ import annotations

from typing import Any

from content_intelligence.sentences import Sentence

# Notes shown per sentence; a long line spanning several shots keeps the first few.
MAX_NOTES_PER_SENTENCE = 2
MAX_SCENE_CHARS = 120


def attach_scenes(sentences: list[Sentence], moments: list[dict[str, Any]]) -> None:
    """Set each sentence's ``scene`` to what is on screen while it is spoken."""
    for sentence in sentences:
        notes: list[str] = []
        for moment in moments:
            if moment["end"] > sentence.start and moment["start"] < sentence.end and moment["shows"] not in notes:
                notes.append(moment["shows"])
            if len(notes) == MAX_NOTES_PER_SENTENCE:
                break
        sentence.scene = "; ".join(notes)[:MAX_SCENE_CHARS]
