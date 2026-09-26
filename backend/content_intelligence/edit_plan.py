"""Turns the director's id-based edit plans into exact, rule-abiding clips.

The model is told the rules; this module enforces them, so a slightly wrong
answer is repaired instead of rendered: ranges are sorted and de-overlapped,
a clip opening mid-thought is walked back to the thought's start, the stitched
length is fitted into the allowed band, the teaser is checked against the hook
rules, and pauses and filler words are cut out of the body (jump cuts).
"""

from __future__ import annotations

from typing import Any

from clip_generation.hook import MAX_HOOK_SECONDS, MIN_HOOK_OFFSET_SECONDS, MIN_HOOK_SECONDS
from content_intelligence.director import BEAT_EFFECTS, DIRECTOR_VERSION, LAYOUTS, RUBRIC
from content_intelligence.sentences import Sentence
from core.logging_config import get_logger

log = get_logger(__name__)

# Padding kept around speech at every cut, so a word's attack and decay survive.
LEAD_PAD = 0.08
TAIL_PAD = 0.15
# Silences longer than this inside a clip are cut out; shorter ones are breath.
JUMP_CUT_MIN_PAUSE = 0.6
JUMP_CUT_KEEP = 0.12
# No piece of a stitched clip may be shorter than this, or the cut reads as a glitch.
MIN_PIECE_SECONDS = 0.5
FILLERS = {"um", "uh", "uhm", "umm", "erm", "er", "hmm", "mm"}
# Rubric weights for the overall 0-1 score: the hook decides whether anyone sees the rest.
RUBRIC_WEIGHTS = {"hook": 0.3, "payoff": 0.25, "standalone": 0.2, "emotion": 0.15, "pacing": 0.1}
# Two clips overlapping more than this share of the shorter one are the same clip.
DUPLICATE_OVERLAP = 0.4


def build_clips(
    plans: list[dict[str, Any]],
    sentences: list[Sentence],
    duration: float,
    min_seconds: float,
    max_seconds: float,
    max_clips: int,
    category: str,
    jump_cuts: bool = True,
) -> list[dict[str, Any]]:
    """Validated clips, best first, at most ``max_clips``."""
    by_id = {s.id: s for s in sentences}
    clips: list[dict[str, Any]] = []
    for plan in plans:
        try:
            clip = _build_clip(plan, sentences, by_id, duration, min_seconds, max_seconds, category, jump_cuts)
        except Exception as exc:
            log.warning("Dropped an edit plan that could not be repaired: %s", exc)
            continue
        if clip is not None:
            clips.append(clip)

    clips.sort(key=lambda c: c["score"], reverse=True)
    kept: list[dict[str, Any]] = []
    for clip in clips:
        if len(kept) >= max_clips:
            break
        if any(_overlap_share(clip, other) > DUPLICATE_OVERLAP for other in kept):
            continue
        kept.append(clip)
    for index, clip in enumerate(sorted(kept, key=lambda c: c["start_time"])):
        clip["id"] = f"highlight_{index}"
    log.info("Edit plans: %d proposed, %d valid, %d kept", len(plans), len(clips), len(kept))
    return kept


def _build_clip(
    plan: dict[str, Any],
    sentences: list[Sentence],
    by_id: dict[int, Sentence],
    duration: float,
    min_seconds: float,
    max_seconds: float,
    category: str,
    jump_cuts: bool,
) -> dict[str, Any] | None:
    ranges = _ranges(plan.get("segments") or [], by_id)
    if not ranges:
        return None
    ranges = _open_on_a_thought(ranges, by_id)
    ranges = _fit_length(ranges, sentences, by_id, min_seconds, max_seconds)
    ids = [i for first, last in ranges for i in range(first, last + 1)]

    spans = [_span(first, last, by_id, duration) for first, last in ranges]
    if jump_cuts:
        spans = _tighten(spans, [w for i in ids for w in by_id[i].words])
    spans = _merge_close(spans)
    body = sum(end - start for start, end in spans)
    if body <= 0:
        return None

    scores = _rubric(plan.get("scores"))
    overall = sum(scores[key] * weight for key, weight in RUBRIC_WEIGHTS.items()) / 10.0
    hook = _hook(plan.get("hook"), ids, by_id, spans)
    text = " ".join(by_id[i].text for i in ids)
    speakers = list(dict.fromkeys(by_id[i].speaker for i in ids if by_id[i].speaker != "-"))
    layout = plan.get("layout") if plan.get("layout") in LAYOUTS else "auto"

    return {
        "start_time": round(spans[0][0], 3),
        "end_time": round(spans[-1][1], 3),
        "edit_spans": [[round(s, 3), round(e, 3)] for s, e in spans],
        "hook_start": hook[0] if hook else None,
        "hook_end": hook[1] if hook else None,
        "score": round(overall, 4),
        "rubric": scores,
        "title": str(plan.get("title") or "").strip()[:100],
        "description": str(plan.get("description") or "").strip(),
        "hashtags": [str(h).strip() for h in plan.get("hashtags") or [] if str(h).strip()][:5],
        "reason": str(plan.get("why") or "").strip(),
        "layout_hint": layout,
        "beats": _beats(plan.get("beats") or [], by_id, spans),
        "transcript_excerpt": text[:1500],
        "speakers": speakers,
        "content_category": category,
        "detection_source": "director",
        "director_version": DIRECTOR_VERSION,
        "reasons": ["director"],
    }


def _ranges(segments: list[Any], by_id: dict[int, Sentence]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for segment in segments:
        try:
            first, last = int(segment.get("from")), int(segment.get("to"))
        except (AttributeError, TypeError, ValueError):
            continue
        first, last = min(first, last), max(first, last)
        if first in by_id and last in by_id:
            ranges.append((first, last))
    ranges.sort()
    merged: list[tuple[int, int]] = []
    for first, last in ranges[:4]:
        if merged and first <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], last))
        else:
            merged.append((first, last))
    return merged


def _open_on_a_thought(ranges: list[tuple[int, int]], by_id: dict[int, Sentence]) -> list[tuple[int, int]]:
    """Walk the clip's opening back past lines that continue an earlier one."""
    first, last = ranges[0]
    steps = 0
    while by_id[first].opens_mid_thought and first - 1 in by_id and steps < 2:
        first -= 1
        steps += 1
    return [(first, last)] + ranges[1:]


def _seconds(ranges: list[tuple[int, int]], by_id: dict[int, Sentence]) -> float:
    return sum(by_id[last].end - by_id[first].start for first, last in ranges)


def _fit_length(
    ranges: list[tuple[int, int]],
    sentences: list[Sentence],
    by_id: dict[int, Sentence],
    min_seconds: float,
    max_seconds: float,
) -> list[tuple[int, int]]:
    ranges = list(ranges)
    # Too long: drop sentences from the end, keeping at least the first one.
    while _seconds(ranges, by_id) > max_seconds:
        first, last = ranges[-1]
        if last > first:
            ranges[-1] = (first, last - 1)
        elif len(ranges) > 1:
            ranges.pop()
        else:
            break
    # Too short: grow forward, then backward, a sentence at a time.
    last_id = sentences[-1].id if sentences else 0
    while _seconds(ranges, by_id) < min_seconds:
        first, last = ranges[-1]
        if last + 1 <= last_id and _seconds(ranges[:-1] + [(first, last + 1)], by_id) <= max_seconds:
            ranges[-1] = (first, last + 1)
            continue
        head_first, head_last = ranges[0]
        if head_first - 1 in by_id and _seconds([(head_first - 1, head_last)] + ranges[1:], by_id) <= max_seconds:
            ranges[0] = (head_first - 1, head_last)
            continue
        break
    return ranges


def _span(first: int, last: int, by_id: dict[int, Sentence], duration: float) -> tuple[float, float]:
    start = by_id[first].start - LEAD_PAD
    end = by_id[last].end + TAIL_PAD
    if first - 1 in by_id:
        start = max(start, by_id[first - 1].end)
    if last + 1 in by_id:
        end = min(end, by_id[last + 1].start)
    return max(0.0, start), min(duration or end, end)


def _tighten(spans: list[tuple[float, float]], words: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """Cut long pauses and standalone filler words out of each span."""
    speech = [
        (w["start"], w["end"]) for w in words
        if w["word"].strip(".,!?;:\"'").lower() not in FILLERS
    ]
    tightened: list[tuple[float, float]] = []
    for span_start, span_end in spans:
        inside = [(s, e) for s, e in speech if e > span_start and s < span_end]
        if not inside:
            tightened.append((span_start, span_end))
            continue
        pieces: list[list[float]] = [[span_start, inside[0][1]]]
        for (s, e), (prev_s, prev_e) in zip(inside[1:], inside[:-1]):
            if s - prev_e >= JUMP_CUT_MIN_PAUSE:
                pieces[-1][1] = prev_e + JUMP_CUT_KEEP
                pieces.append([s - JUMP_CUT_KEEP, e])
            else:
                pieces[-1][1] = e
        pieces[-1][1] = span_end
        tightened.extend((a, b) for a, b in pieces)
    return tightened


def _merge_close(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Rejoin pieces too short to stand alone, and gaps too small to be worth a cut."""
    merged: list[list[float]] = []
    for start, end in spans:
        if merged and (start - merged[-1][1] < 0.15 or end - start < MIN_PIECE_SECONDS or merged[-1][1] - merged[-1][0] < MIN_PIECE_SECONDS):
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def _hook(value: Any, ids: list[int], by_id: dict[int, Sentence], spans: list[tuple[float, float]]) -> tuple[float, float] | None:
    try:
        hook_id = int(value or 0)
    except (TypeError, ValueError):
        return None
    if hook_id not in ids or hook_id == ids[0]:
        return None
    sentence = by_id[hook_id]
    words = sentence.words or [{"start": sentence.start, "end": sentence.end}]
    start = words[0]["start"]
    end = words[-1]["end"]
    if end - start > MAX_HOOK_SECONDS:
        within = [w for w in words if w["end"] - start <= MAX_HOOK_SECONDS]
        if not within:
            return None
        end = within[-1]["end"]
    if end - start < MIN_HOOK_SECONDS or start < spans[0][0] + MIN_HOOK_OFFSET_SECONDS:
        return None
    return round(start, 3), round(end, 3)


def _beats(beats: list[Any], by_id: dict[int, Sentence], spans: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Beats in source seconds, kept only where they land inside the clip."""
    placed: list[dict[str, Any]] = []
    for beat in beats[:4]:
        if not isinstance(beat, dict) or beat.get("fx") not in BEAT_EFFECTS:
            continue
        try:
            sentence = by_id[int(beat.get("at"))]
        except (KeyError, TypeError, ValueError):
            continue
        word = str(beat.get("word") or "").strip()
        at = sentence.start
        for w in sentence.words:
            if word and w["word"].strip(".,!?;:\"'").lower() == word.strip(".,!?;:\"'").lower():
                at = w["start"]
                break
        if any(start <= at < end for start, end in spans):
            placed.append({"t": round(at, 3), "fx": beat["fx"], "word": word})
    return placed


def _rubric(value: Any) -> dict[str, float]:
    raw = value if isinstance(value, dict) else {}
    scores: dict[str, float] = {}
    for key in RUBRIC:
        try:
            score = float(raw.get(key, 5))
        except (TypeError, ValueError):
            score = 5.0
        scores[key] = round(min(10.0, max(1.0, score / 10.0 if score > 10 else score)), 1)
    return scores


def _overlap_share(a: dict[str, Any], b: dict[str, Any]) -> float:
    shared = sum(
        max(0.0, min(ae, be) - max(as_, bs))
        for as_, ae in a["edit_spans"] for bs, be in b["edit_spans"]
    )
    shorter = min(
        sum(e - s for s, e in a["edit_spans"]),
        sum(e - s for s, e in b["edit_spans"]),
    )
    return shared / shorter if shorter > 0 else 0.0
