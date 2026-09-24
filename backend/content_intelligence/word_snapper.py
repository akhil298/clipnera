from __future__ import annotations

from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)

DEFAULT_MIN_DURATION = 15.0
DEFAULT_MAX_DURATION = 60.0
DEFAULT_SEARCH_WINDOW = 1.5
DEFAULT_MAX_LEAD = 0.35
DEFAULT_MAX_TAIL = 0.45
# Furthest a boundary may travel to reach the edge of the sentence it cuts.
DEFAULT_SENTENCE_REACH = 10.0

_SENTENCE_ENDINGS = (".", "?", "!")
# A clip whose first sentence opens on one of these is picking up a thought
# that started earlier ("Not for one hour..."), so it needs the sentence before.
_CONTINUATION_OPENERS = frozenset({
    "and", "but", "so", "because", "not", "or", "which", "that", "then", "also", "plus",
})


def snap_clip_to_sentences(
    start: float,
    end: float,
    segments: list[dict[str, Any]],
    min_duration: float = 0.0,
    max_duration: float = DEFAULT_MAX_DURATION,
    max_reach: float = DEFAULT_SENTENCE_REACH,
) -> tuple[float, float]:
    """Widen clip bounds to whole sentences so a clip never opens or closes mid-thought.

    Word snapping only guarantees a cut lands between words; a model-proposed
    span still routinely starts on a sentence's second half or stops before its
    last clause. The start moves back to the beginning of its sentence (and one
    sentence further when that sentence opens on a connective), the end moves
    forward to the next sentence end. If that overruns ``max_duration`` the end
    is pulled back to the last sentence end that fits instead.

    Transcripts without punctuation carry no sentence information, so the input
    is returned unchanged for them.
    """
    usable = sorted(
        (s for s in segments if str(s.get("text", "")).strip()),
        key=lambda s: float(s.get("start", 0.0)),
    )
    ends_sentence = [str(s.get("text", "")).rstrip().endswith(_SENTENCE_ENDINGS) for s in usable]
    if not any(ends_sentence):
        return start, end

    first = next((i for i, s in enumerate(usable) if float(s.get("end", 0.0)) > start), None)
    last = next((i for i in range(len(usable) - 1, -1, -1) if float(usable[i].get("start", 0.0)) < end), None)
    if first is None or last is None or last < first:
        return start, end

    def sentence_start(index: int) -> int:
        while index > 0 and not ends_sentence[index - 1]:
            index -= 1
        return index

    def seg_start(index: int) -> float:
        return float(usable[index].get("start", 0.0))

    def seg_end(index: int) -> float:
        return float(usable[index].get("end", 0.0))

    head = sentence_start(first)
    if start - seg_start(head) > max_reach:
        head = first
    if head > 0 and _opens_mid_thought(usable[head].get("text", "")):
        previous = sentence_start(head - 1)
        if start - seg_start(previous) <= max_reach:
            head = previous

    tail = last
    while tail < len(usable) - 1 and not ends_sentence[tail] and seg_end(tail + 1) - end <= max_reach:
        tail += 1

    new_start = seg_start(head)
    new_end = seg_end(tail)
    if max_duration > 0 and new_end - new_start > max_duration:
        fitting = [
            seg_end(i) for i in range(head, tail + 1)
            if ends_sentence[i] and min_duration <= seg_end(i) - new_start <= max_duration
        ]
        if not fitting:
            return start, end
        new_end = max(fitting)

    if new_end <= new_start:
        return start, end
    return round(new_start, 3), round(new_end, 3)


def _opens_mid_thought(text: str) -> bool:
    words = str(text).strip().split(maxsplit=1)
    return bool(words) and words[0].strip(",.;:!?\"'").lower() in _CONTINUATION_OPENERS


def snap_clip_to_words(
    start: float,
    end: float,
    words: list[dict[str, Any]],
    video_duration: float,
    min_duration: float | None = None,
    max_duration: float = DEFAULT_MAX_DURATION,
    search_window: float = DEFAULT_SEARCH_WINDOW,
    max_lead: float = DEFAULT_MAX_LEAD,
    max_tail: float = DEFAULT_MAX_TAIL,
) -> tuple[float, float]:
    """Snap proposed clip boundaries onto word boundaries plus surrounding silence.

    LLMs and segment detectors are bad at millisecond precision; word timestamps
    from Whisper are ground truth. Cuts land in pauses instead of mid-word.

    ``words`` is ``[{'start','end','text'}, ...]`` or Whisper segments carrying
    word-level timestamps. ``video_duration`` is the duration of the media the
    timestamps refer to, not the length of the clip.

    ``min_duration`` is strict when passed: if snapping cannot produce a clip
    that long, the original bounds are returned unchanged. Left unset it is
    advisory, so subtitle alignment on a short clip still gets snapped bounds
    instead of silently falling back to unsnapped input.

    Returns ``(start, end)``, always inside ``[0, video_duration]``.
    """
    duration_limit = max(0.0, float(video_duration))
    start = min(max(0.0, float(start)), duration_limit)
    end = min(max(start, float(end)), duration_limit)
    original = (round(start, 3), round(end, 3))

    strict_min = min_duration is not None
    required_min = float(min_duration) if strict_min else 0.0
    if max_duration > 0:
        # A minimum above the maximum can never be satisfied; the cap wins.
        required_min = min(required_min, max_duration)

    if not words or end <= start:
        return original

    flat_words = _flatten_words(words)
    if not flat_words:
        return original

    starts = sorted(w["start"] for w in flat_words)
    ends = sorted(w["end"] for w in flat_words)

    new_start = start
    start_candidates = [s for s in starts if abs(s - new_start) <= search_window]
    if start_candidates:
        word_start = min(start_candidates, key=lambda s: abs(s - new_start))
        prev_ends = [e for e in ends if e <= word_start]
        lead = min(max_lead, max(0.0, word_start - max(prev_ends)) / 2.0) if prev_ends else max_lead
        new_start = max(0.0, word_start - lead)

    new_end = end
    end_candidates = [e for e in ends if abs(e - new_end) <= search_window]
    if end_candidates:
        word_end = min(end_candidates, key=lambda e: abs(e - new_end))
        next_starts = [s for s in starts if s >= word_end]
        tail = min(max_tail, max(0.0, min(next_starts) - word_end) / 2.0) if next_starts else max_tail
        new_end = min(duration_limit, word_end + tail)

    if required_min > 0 and new_end - new_start < required_min:
        target = new_start + required_min
        later = sorted(e for e in ends if e >= target)
        if later and later[0] - new_start <= max_duration:
            new_end = min(duration_limit, later[0] + 0.2)
        elif strict_min:
            # The caller demanded a length the transcript cannot supply.
            log.debug(
                "Word snapping could not reach min_duration=%.2fs; keeping original bounds",
                required_min,
            )
            return original

    if max_duration > 0 and new_end - new_start > max_duration:
        target = new_start + max_duration
        earlier = [e for e in ends if new_start < e <= target]
        new_end = max(earlier) + 0.2 if earlier else target
        new_end = min(new_end, new_start + max_duration, duration_limit)

    if new_end <= new_start:
        return original
    if strict_min and new_end - new_start < required_min:
        return original

    return (round(new_start, 3), round(new_end, 3))


def snap_clip_to_segments(
    start: float,
    end: float,
    segments: list[dict[str, Any]],
    video_duration: float,
    min_duration: float = DEFAULT_MIN_DURATION,
    max_duration: float = DEFAULT_MAX_DURATION,
) -> tuple[float, float]:
    """Snap clip boundaries to segment boundaries (coarser than word-level)."""
    if not segments:
        return (round(start, 3), round(end, 3))

    seg_starts = sorted(float(s.get("start", 0.0)) for s in segments)
    seg_ends = sorted(float(s.get("end", 0.0)) for s in segments)

    new_start = float(start)
    start_matches = [s for s in seg_starts if abs(s - new_start) <= 0.5]
    if not start_matches:
        before = [s for s in seg_starts if s <= new_start]
        after = [s for s in seg_starts if s > new_start]
        if before and after:
            new_start = max(0.0, before[-1] if new_start - before[-1] < 0.5 else after[0])
        elif after:
            new_start = max(0.0, after[0])

    new_end = float(end)
    end_matches = [e for e in seg_ends if abs(e - new_end) <= 0.5]
    if not end_matches:
        before = [e for e in seg_ends if e <= new_end]
        after = [e for e in seg_ends if e > new_end]
        if after and before:
            new_end = min(float(video_duration), after[0] if after[0] - new_end < 0.5 else before[-1])
        elif before:
            new_end = min(float(video_duration), before[-1])

    if new_end - new_start < min_duration:
        return (round(start, 3), round(end, 3))

    if new_end - new_start > max_duration:
        return (round(start, 3), round(end, 3))

    return (round(new_start, 3), round(new_end, 3))


def _flatten_words(words: list[dict[str, Any]]) -> list[dict[str, float]]:
    """Extract flat [{'start','end'}] from segments or word lists."""
    flat: list[dict[str, float]] = []
    for item in words:
        if item.get("words"):
            for w in item["words"]:
                w_start = float(w.get("start", w.get("s", 0.0)))
                w_end = float(w.get("end", w.get("e", 0.0)))
                if w_end > w_start:
                    flat.append({"start": w_start, "end": w_end})
        elif item.get("start") is not None and item.get("end") is not None:
            w_start = float(item["start"])
            w_end = float(item["end"])
            if w_end > w_start:
                flat.append({"start": w_start, "end": w_end})
    flat.sort(key=lambda w: w["start"])
    return flat
