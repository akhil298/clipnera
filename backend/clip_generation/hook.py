"""The teaser played before a clip: its most gripping line, shown first.

The rendered file is ``[hook.start, hook.end)`` followed by
``[clip_start, clip_end)``, both in source-video seconds. Everything that times
captions against that file goes through :func:`on_output_timeline`, so the
burner and the editor agree on where each word lands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# A teaser shorter than this is a word, not a line; longer and it gives the
# clip away instead of teasing it.
MIN_HOOK_SECONDS = 1.5
MAX_HOOK_SECONDS = 6.0
# A hook taken from the clip's opening would play the same line twice in a row.
MIN_HOOK_OFFSET_SECONDS = 3.0

_NON_WORD = re.compile(r"[^\w']+")


@dataclass(frozen=True)
class Hook:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start

    @classmethod
    def from_values(cls, start: Any, end: Any) -> Hook | None:
        """The stored hook, or ``None`` for a clip saved without one."""
        if start is None or end is None:
            return None
        return cls(float(start), float(end))


def locate_hook(
    quote: str,
    transcript_segments: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
) -> Hook | None:
    """Find the model's quoted line in the clip's word timings.

    The model quotes text rather than giving timestamps because transcript
    lines are whole segments, far coarser than the few seconds a hook runs;
    word timings pin it exactly. Returns ``None`` when the quote is not found
    or the matched span is not usable as a teaser.
    """
    target = _tokens(quote)
    if not target:
        return None

    words = [
        (float(word.get("start", 0.0)), float(word.get("end", 0.0)), token)
        for segment in transcript_segments
        for word in segment.get("words") or []
        if float(word.get("start", 0.0)) >= clip_start and float(word.get("end", 0.0)) <= clip_end
        if (token := _normalize(str(word.get("word", word.get("text", "")))))
    ]
    spoken = [token for _, _, token in words]
    for index in range(len(spoken) - len(target) + 1):
        if spoken[index:index + len(target)] == target:
            hook = Hook(words[index][0], words[index + len(target) - 1][1])
            return hook if _usable(hook, clip_start) else None
    return None


def on_output_timeline(
    items: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    hook: Hook | None,
) -> tuple[float, list[dict[str, Any]]]:
    """Lay absolute-time items (words, subtitle lines) out on the rendered file.

    Returns ``(origin, items)`` such that ``item["start"] - origin`` is the
    item's position in the output. Callers keep rebasing against a single
    origin exactly as they did before hooks existed: the teaser's items are
    shifted to sit in the first ``hook.duration`` seconds, and the clip's own
    items are left in place with the origin moved back by that much.
    """
    if hook is None:
        return clip_start, items

    origin = clip_start - hook.duration
    teaser = _within(items, hook.start, hook.end, shift=origin - hook.start)
    body = _within(items, clip_start, clip_end, shift=0.0)
    return origin, teaser + body


def _within(items: list[dict[str, Any]], start: float, end: float, shift: float) -> list[dict[str, Any]]:
    """Items overlapping ``[start, end)``, clamped to it and moved by ``shift``."""
    return [
        {
            **item,
            "start": max(start, float(item.get("start", 0.0))) + shift,
            "end": min(end, float(item.get("end", 0.0))) + shift,
        }
        for item in items
        if float(item.get("end", 0.0)) > start and float(item.get("start", 0.0)) < end
    ]


def _usable(hook: Hook, clip_start: float) -> bool:
    return (
        MIN_HOOK_SECONDS <= hook.duration <= MAX_HOOK_SECONDS
        and hook.start >= clip_start + MIN_HOOK_OFFSET_SECONDS
    )


def _tokens(text: str) -> list[str]:
    return [token for token in map(_normalize, text.split()) if token]


def _normalize(word: str) -> str:
    """Compare words without case or punctuation, as the model may drop either."""
    return _NON_WORD.sub("", word.lower())
