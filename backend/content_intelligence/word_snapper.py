from __future__ import annotations

from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)

DEFAULT_MIN_DURATION = 15.0
DEFAULT_MAX_DURATION = 60.0
DEFAULT_SEARCH_WINDOW = 1.5
DEFAULT_MAX_LEAD = 0.35
DEFAULT_MAX_TAIL = 0.45


def snap_clip_to_words(
    start: float,
    end: float,
    words: list[dict[str, Any]],
    video_duration: float,
    min_duration: float = DEFAULT_MIN_DURATION,
    max_duration: float = DEFAULT_MAX_DURATION,
    search_window: float = DEFAULT_SEARCH_WINDOW,
    max_lead: float = DEFAULT_MAX_LEAD,
    max_tail: float = DEFAULT_MAX_TAIL,
) -> tuple[float, float]:
    """Snap proposed clip boundaries onto word boundaries plus surrounding silence.

    LLMs and segment detectors are bad at millisecond precision; word timestamps
    from Whisper are ground truth. Cuts land in pauses instead of mid-word.

    words: [{'start','end','text'}, ...] sorted by start (or Whisper segments
    with word-level timestamps).
    Returns (start, end); falls back to the input if snapping cannot satisfy
    the duration bounds.
    """
    original = (round(float(start), 3), round(float(end), 3))
    if not words:
        return original

    flat_words = _flatten_words(words)
    if not flat_words:
        return original

    starts = sorted(w["start"] for w in flat_words)
    ends = sorted(w["end"] for w in flat_words)

    new_start = float(start)
    start_candidates = [s for s in starts if abs(s - new_start) <= search_window]
    if start_candidates:
        word_start = min(start_candidates, key=lambda s: abs(s - new_start))
        prev_ends = [e for e in ends if e <= word_start]
        if prev_ends:
            gap = max(0.0, word_start - max(prev_ends))
            lead = min(max_lead, gap / 2.0)
        else:
            lead = max_lead
        new_start = max(0.0, word_start - lead)

    new_end = float(end)
    end_candidates = [e for e in ends if abs(e - new_end) <= search_window]
    if end_candidates:
        word_end = min(end_candidates, key=lambda e: abs(e - new_end))
        next_starts = [s for s in starts if s >= word_end]
        if next_starts:
            gap = max(0.0, min(next_starts) - word_end)
            tail = min(max_tail, gap / 2.0)
        else:
            tail = max_tail
        new_end = min(float(video_duration), word_end + tail)

    if new_end - new_start < min_duration:
        target = new_start + min_duration
        later = sorted(e for e in ends if e >= target)
        if later and later[0] - new_start <= max_duration:
            new_end = min(float(video_duration), later[0] + 0.2)
        else:
            return original

    if new_end - new_start > max_duration:
        target = new_start + max_duration
        earlier = [e for e in ends if new_start < e <= target]
        new_end = max(earlier) + 0.2 if earlier else target
        new_end = min(new_end, new_start + max_duration, float(video_duration))

    if new_end <= new_start or new_end - new_start < min_duration:
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
