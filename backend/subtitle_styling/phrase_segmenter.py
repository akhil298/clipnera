from __future__ import annotations

from typing import Any

from core.logging_config import get_logger
from subtitle_styling.ass_generator import escape_ass

log = get_logger(__name__)

DEFAULT_MIN_DURATION = 5.0
DEFAULT_MAX_DURATION = 15.0
DEFAULT_MAX_GAP = 1.5
DEFAULT_PAD = 0.08
SENTENCE_BOUNDARIES = ".!?"
MAX_LINE_CHARS = 42


def _extract_words(segments: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    words: list[dict[str, float | str]] = []
    for seg in segments:
        if seg.get("words"):
            for w in seg["words"]:
                w_start = float(w.get("start", w.get("s", 0.0)))
                w_end = float(w.get("end", w.get("e", 0.0)))
                w_text = str(w.get("word", w.get("text", "")))
                if w_text.strip() and w_end > w_start:
                    words.append({"start": w_start, "end": w_end, "text": w_text})
        else:
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
            text = str(seg.get("text", ""))
            if text.strip() and end > start:
                words.append({"start": start, "end": end, "text": text})
    words.sort(key=lambda w: float(w["start"]))
    return words


def _gap_after(words: list[dict[str, float | str]], index: int) -> float:
    if index + 1 >= len(words):
        return 0.0
    return float(words[index + 1]["start"]) - float(words[index]["end"])


def _ends_sentence(word: dict[str, float | str]) -> bool:
    text = str(word.get("text", "")).strip()
    return text and text[-1] in SENTENCE_BOUNDARIES


def _word_count_chars(words: list[dict[str, float | str]], start: int, end: int) -> int:
    return sum(len(str(w["text"])) for w in words[start:end])


def segment_phrases(
    segments: list[dict[str, Any]],
    min_duration: float = DEFAULT_MIN_DURATION,
    max_duration: float = DEFAULT_MAX_DURATION,
    max_gap: float = DEFAULT_MAX_GAP,
    pad: float = DEFAULT_PAD,
) -> list[dict[str, Any]]:
    """Segment transcript into phrase-aware chunks (Recordly-style).

    Splits on sentence boundaries combined with silence detection:
    - A phrase break occurs when the gap to the next word exceeds ``max_gap``
      seconds AND the current word ends a sentence.
    - Falls back to splitting by gap alone when no sentence boundary is found.
    - Each phrase is clamped to [min_duration, max_duration].
    - A small pad (lead-in) is removed from the start.
    """
    words = _extract_words(segments)
    if not words:
        return []

    phrases: list[list[dict[str, float | str]]] = []
    current: list[dict[str, float | str]] = []

    for i, word in enumerate(words):
        current.append(word)

        gap = _gap_after(words, i)
        at_sentence_end = _ends_sentence(word)
        current_duration = float(word["end"]) - float(current[0]["start"])

        should_break = False
        if gap >= max_gap and at_sentence_end:
            should_break = True
        if not should_break and gap >= max_gap and current_duration >= min_duration:
            should_break = True
        if current_duration >= max_duration and at_sentence_end:
            should_break = True

        if should_break:
            phrases.append(current)
            current = []

    if current:
        phrases.append(current)

    result: list[dict[str, Any]] = []
    for phrase_words in phrases:
        start = float(phrase_words[0]["start"]) - pad
        end = float(phrase_words[-1]["end"])
        start = max(0.0, start)
        if end - start >= min_duration:
            text = " ".join(str(w["text"]).strip() for w in phrase_words).strip()
            result.append({
                "start_time": round(start, 3),
                "end_time": round(end, 3),
                "text": escape_ass(text),
                "word_count": len(phrase_words),
            })

    if not result and words:
        start = max(0.0, float(words[0]["start"]) - pad)
        end = float(words[-1]["end"])
        text = " ".join(str(w["text"]).strip() for w in words).strip()
        result.append({
            "start_time": round(start, 3),
            "end_time": round(end, 3),
            "text": escape_ass(text),
            "word_count": len(words),
        })

    return result


def segment_for_captions(
    segments: list[dict[str, Any]],
    max_chars: int = MAX_LINE_CHARS,
    max_words_per_line: int = 7,
) -> list[dict[str, Any]]:
    """Build caption-style segments from transcript, grouping words by
    display width rather than sentence boundaries — for the subtitle_styling
    pipeline that needs readable on-screen lines."""
    words = _extract_words(segments)
    if not words:
        return []

    result: list[dict[str, Any]] = []
    current: list[dict[str, float | str]] = []
    current_chars = 0

    for word in words:
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        word_len = len(text)

        if current and (
            current_chars + 1 + word_len > max_chars
            or len(current) >= max_words_per_line
            or _ends_sentence(current[-1])
        ):
            if current:
                start = float(current[0]["start"])
                end = float(current[-1]["end"])
                text = " ".join(str(w["text"]).strip() for w in current).strip()
                result.append({
                    "start_time": round(start, 3),
                    "end_time": round(end, 3),
                    "text": escape_ass(text),
                })
            current = []
            current_chars = 0

        if current:
            current_chars += 1
        current_chars += word_len
        current.append(word)

    if current:
        start = float(current[0]["start"])
        end = float(current[-1]["end"])
        text = " ".join(str(w["text"]).strip() for w in current).strip()
        result.append({
            "start_time": round(start, 3),
            "end_time": round(end, 3),
            "text": escape_ass(text),
        })

    return result
