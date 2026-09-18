from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clients.ai.groq import estimate_tokens
from core.logging_config import get_logger

log = get_logger(__name__)

# Seconds of transcript repeated at each window boundary, so a strong moment that
# straddles a split is fully visible to at least one window.
DEFAULT_OVERLAP_SECONDS = 20.0


@dataclass
class TranscriptWindow:
    """A contiguous slice of transcript small enough for one LLM request."""

    index: int
    start: float
    end: float
    segments: list[dict[str, Any]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return format_segments(self.segments)

    @property
    def token_estimate(self) -> int:
        return estimate_tokens(self.text)


def format_segment(segment: dict[str, Any]) -> str:
    start = float(segment.get("start", 0.0))
    end = float(segment.get("end", 0.0))
    speaker = segment.get("speaker") or "Unknown speaker"
    text = str(segment.get("text", "")).strip()
    return f"[{start:.3f}-{end:.3f}] {speaker}: {text}"


def format_segments(segments: list[dict[str, Any]]) -> str:
    return "\n".join(format_segment(segment) for segment in segments)


def build_transcript_windows(
    segments: list[dict[str, Any]],
    budget_tokens: int,
    overlap_seconds: float = DEFAULT_OVERLAP_SECONDS,
) -> list[TranscriptWindow]:
    """Split a transcript into windows that each fit ``budget_tokens``.

    Replaces the previous behaviour of handing the whole transcript to a client
    that silently kept only its tail, which made every clip come from the last
    few minutes of a long video.
    """
    usable = [s for s in segments if str(s.get("text", "")).strip()]
    if not usable:
        return []
    if budget_tokens <= 0:
        raise ValueError("budget_tokens must be positive")

    windows: list[TranscriptWindow] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0

    for segment in usable:
        segment_tokens = estimate_tokens(format_segment(segment)) + 1
        if current and current_tokens + segment_tokens > budget_tokens:
            windows.append(_make_window(len(windows), current))
            current = _overlap_tail(current, overlap_seconds)
            current_tokens = sum(estimate_tokens(format_segment(s)) + 1 for s in current)
        current.append(segment)
        current_tokens += segment_tokens

    if current:
        windows.append(_make_window(len(windows), current))

    log.info(
        "Transcript split into %d window(s): budget=%d tokens, total=%d tokens, span=%.1fs",
        len(windows),
        budget_tokens,
        estimate_tokens(format_segments(usable)),
        float(usable[-1].get("end", 0.0)) - float(usable[0].get("start", 0.0)),
    )
    return windows


def _make_window(index: int, segments: list[dict[str, Any]]) -> TranscriptWindow:
    return TranscriptWindow(
        index=index,
        start=float(segments[0].get("start", 0.0)),
        end=float(segments[-1].get("end", 0.0)),
        segments=list(segments),
    )


def _overlap_tail(segments: list[dict[str, Any]], overlap_seconds: float) -> list[dict[str, Any]]:
    """Trailing segments within ``overlap_seconds`` of the window end."""
    if overlap_seconds <= 0 or not segments:
        return []
    cutoff = float(segments[-1].get("end", 0.0)) - overlap_seconds
    tail = [s for s in segments if float(s.get("start", 0.0)) >= cutoff]
    # Never let the overlap become the whole window, or splitting stops making progress.
    if len(tail) >= len(segments):
        tail = segments[-1:]
    return list(tail)


def allocate_per_window(total: int, window_count: int) -> int:
    """How many moments to request from each window to reach ``total`` overall.

    Asks for a little extra, since the reduce step drops duplicates found in the
    overlap regions and filters out-of-bounds moments.
    """
    if window_count <= 0:
        return total
    return max(2, -(-total // window_count) + 1)


def deduplicate_moments(
    moments: list[dict[str, Any]],
    overlap_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Merge moments covering the same span, keeping the highest scoring one.

    Window overlap means the same moment can be returned twice, and the model
    sometimes proposes near-identical spans within one window.
    """
    ordered = sorted(
        moments,
        key=lambda m: (-float(m.get("score", 0.0)), float(m.get("start_time", 0.0))),
    )
    kept: list[dict[str, Any]] = []
    for moment in ordered:
        start = float(moment.get("start_time", 0.0))
        end = float(moment.get("end_time", start))
        duration = max(1e-6, end - start)
        duplicate = False
        for existing in kept:
            e_start = float(existing.get("start_time", 0.0))
            e_end = float(existing.get("end_time", e_start))
            overlap = min(end, e_end) - max(start, e_start)
            if overlap <= 0:
                continue
            shorter = min(duration, max(1e-6, e_end - e_start))
            if overlap / shorter >= overlap_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(moment)

    if len(kept) < len(moments):
        log.info("Deduplicated moments: %d -> %d", len(moments), len(kept))
    return sorted(kept, key=lambda m: float(m.get("start_time", 0.0)))
