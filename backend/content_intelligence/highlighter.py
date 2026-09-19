from __future__ import annotations

import json
import math
from typing import Any

from content_intelligence.transcript_windows import (
    TranscriptWindow,
    allocate_per_window,
    build_transcript_windows,
    deduplicate_moments,
)
from core.logging_config import get_logger
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

log = get_logger(__name__)

MIN_CLIP_DURATION = 20.0
MAX_CLIP_DURATION = 60.0
# Clips kept per hour of source. A ceiling on density rather than a target;
# scoring still decides which ones survive. One per three minutes is around
# what a competitive short-form tool returns, and past that the extra clips are
# mostly weaker variants nobody publishes -- while every one of them costs a
# metadata call.
MAX_CLIPS_PER_HOUR = 20.0
# No matter how short the video, offer at least this many candidates, as long
# as the transcript can supply them.
MIN_CLIPS = 5
# Two kept clips should not start within this many seconds of each other, so a
# model that fixates on one passage cannot fill the whole result set.
MIN_CLIP_SPACING_SECONDS = 15.0

# Output cap per window. A moment costs roughly 120 tokens of JSON, so this
# covers a full window's worth with room for a reasoning model's preamble.
# Too low and the reply is truncated mid-JSON, which parses to nothing and
# silently empties the window.
WINDOW_MAX_OUTPUT_TOKENS = 2600
# Most moments to request from any single window. Asking one window for a long
# list produces padding and risks truncating the reply; a higher target is met
# by having more windows, not longer answers.
MAX_MOMENTS_PER_WINDOW = 10

# Enforced server-side by providers that support schema-constrained output, so
# the reply cannot come back missing a field or with the wrong type. Providers
# without it fall back to the prompt's schema block plus tolerant parsing.
_SCORE = {"type": "number", "minimum": 0, "maximum": 1}
MOMENTS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "moments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "number", "minimum": 0},
                    "end_time": {"type": "number", "minimum": 0},
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "score": _SCORE,
                    "scores": {
                        "type": "object",
                        "properties": {
                            "relevance": _SCORE,
                            "importance": _SCORE,
                            "emotional_impact": _SCORE,
                            "information_value": _SCORE,
                            "standalone_context": _SCORE,
                            "social_media_value": _SCORE,
                            "current_relevance": _SCORE,
                        },
                        "required": [
                            "relevance", "importance", "emotional_impact", "information_value",
                            "standalone_context", "social_media_value", "current_relevance",
                        ],
                        "additionalProperties": False,
                    },
                    "speakers": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["start_time", "end_time", "title", "reason", "score", "scores", "speakers"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["moments"],
    "additionalProperties": False,
}
# Tokens reserved for the instruction block wrapped around each window.
PROMPT_OVERHEAD_TOKENS = 500


# Generic hooks that read as interesting in any category. Used to rank
# transcript windows when the model is unavailable.
_FALLBACK_ENGAGEMENT_SIGNALS = (
    "but ", "actually", "secret", "never", "always", "truth", "mistake", "wrong",
    "crazy", "insane", "shocking", "reason", "because", "problem", "why",
    "how to", "the thing is", "believe", "realize", "learned", "first time",
    "biggest", "best", "worst", "money", "free", "wait",
)


class HighlightDetector:
    def __init__(self, text_client: Any | None = None) -> None:
        self._text_client = text_client

    def _input_token_budget(self) -> int:
        """Prompt budget for one window, from the configured provider.

        Falls back to a conservative figure when the client predates the
        contract, so a custom or stubbed client still works.
        """
        getter = getattr(self._text_client, "input_token_budget", None)
        if callable(getter):
            try:
                return int(getter(WINDOW_MAX_OUTPUT_TOKENS))
            except Exception as exc:
                log.warning("Provider did not report a token budget (%s); using the default", exc)
        return 4096

    async def detect(self, video_path: str, transcript_segments: list[dict], analysis: dict, clip_settings: dict[str, Any] | None = None) -> list[dict]:
        duration = self._probe_duration(video_path)
        category = analysis.get("classification", {}).get("category", "unknown")
        settings = clip_settings or {}

        min_clip_duration = float(settings.get("min_clip_duration") or MIN_CLIP_DURATION)
        max_clip_duration = float(settings.get("max_clip_duration") or MAX_CLIP_DURATION)
        max_clips_per_hour = float(settings.get("max_clips_per_hour") or MAX_CLIPS_PER_HOUR)
        max_clips = self._max_clips(duration, max_clips_per_hour, settings.get("max_clips"))

        source = "llm"
        candidates = await self._detect_with_llm(
            transcript_segments, analysis, duration, category,
            min_clip_duration, max_clip_duration, target_clips=max_clips,
        )
        if not candidates and transcript_segments:
            log.warning("LLM returned no highlights; falling back to transcript-based clip detection")
            source = "transcript_fallback"
            candidates = self._detect_from_transcript(
                transcript_segments, category, duration, min_clip_duration, max_clip_duration,
            )

        if not candidates:
            log.warning("LLM and fallback both returned no highlights; returning empty clip list")
            return []

        # Duration bounds always apply. They used to be enforced only when the
        # caller passed explicit settings, so a model that proposed four-second
        # moments had them rendered verbatim; and enforcement dropped anything
        # too short instead of growing it, which threw away good moments.
        candidates = self._fit_durations(
            candidates, transcript_segments, duration, min_clip_duration, max_clip_duration,
        )
        candidates = deduplicate_moments(candidates)
        candidates = self._select_spread(candidates, max_clips, duration)

        for i, candidate in enumerate(candidates):
            candidate["id"] = f"highlight_{i}"
            candidate["content_category"] = category
            candidate["detection_source"] = source

        log.info(
            "Highlight detection complete",
            extra={
                "video_duration": round(duration, 2),
                "min_clip_duration": min_clip_duration,
                "max_clip_duration": max_clip_duration,
                "max_clips_per_hour": max_clips_per_hour,
                "selected_clips": len(candidates),
                "source": source,
                "clip_ranges": [
                    {
                        "id": c.get("id", f"highlight_{idx}"),
                        "start": round(c.get("start_time", 0), 2),
                        "end": round(c.get("end_time", 0), 2),
                        "duration": round(c.get("end_time", 0) - c.get("start_time", 0), 2),
                        "score": round(c.get("score", 0), 2),
                        "reasons": c.get("reasons", []),
                    }
                    for idx, c in enumerate(candidates)
                ],
            },
        )

        return candidates

    async def _detect_with_llm(
        self,
        transcript_segments: list[dict[str, Any]],
        analysis: dict[str, Any],
        duration: float,
        category: str,
        min_clip_duration: float = MIN_CLIP_DURATION,
        max_clip_duration: float = MAX_CLIP_DURATION,
        target_clips: int = 10,
    ) -> list[dict[str, Any]]:
        """Ask the model for highlights across the whole transcript.

        The transcript is split into windows that fit the model's input budget
        and each is scored independently, because a long transcript sent as one
        prompt is truncated to its tail and every clip then comes from the end
        of the video.
        """
        # Sized against the configured provider, not a hard-coded one: Groq's
        # free tier forces several small windows, while a 1M-context provider
        # takes the whole transcript in a single request.
        budget = self._input_token_budget() - PROMPT_OVERHEAD_TOKENS
        windows = build_transcript_windows(transcript_segments, budget_tokens=budget)
        if not windows:
            log.warning("No usable transcript segments for highlight detection")
            return []

        per_window = min(MAX_MOMENTS_PER_WINDOW, allocate_per_window(target_clips, len(windows)))
        log.info(
            "LLM highlight detection over %d window(s): budget=%d tokens, requesting %d moment(s) per window",
            len(windows), budget, per_window,
        )

        collected: list[dict[str, Any]] = []
        failed_windows = 0
        for window in windows:
            moments = await self._detect_in_window(
                window=window,
                analysis=analysis,
                duration=duration,
                category=category,
                min_clip_duration=min_clip_duration,
                max_clip_duration=max_clip_duration,
                max_moments=per_window,
            )
            if moments is None:
                failed_windows += 1
                continue
            collected.extend(
                self._build_candidate(item, transcript_segments, window, duration)
                for item in moments
            )

        candidates = [c for c in collected if c is not None]
        if failed_windows:
            log.warning("LLM highlight detection failed for %d/%d window(s)", failed_windows, len(windows))

        deduped = deduplicate_moments(candidates)
        log.info(
            "LLM highlight detection complete: windows=%d, raw=%d, deduped=%d",
            len(windows), len(candidates), len(deduped),
        )
        return deduped

    async def _detect_in_window(
        self,
        window: TranscriptWindow,
        analysis: dict[str, Any],
        duration: float,
        category: str,
        min_clip_duration: float,
        max_clip_duration: float,
        max_moments: int,
    ) -> list[dict[str, Any]] | None:
        """Return the model's moments for one window, or None if the call failed."""
        research = analysis.get("topic_research", {})
        # Left to itself the model takes its moments from the opening of the
        # excerpt and ignores the rest, so it is told where to look.
        anchors = self._distribution_anchors(window.start, window.end, max_moments)
        prompt = f"""Select the best standalone short-form video clips from this transcript excerpt. Return only valid JSON as an object with a "moments" array.

Video category: {category}
Full video duration: {duration:.3f} seconds
This excerpt covers {window.start:.3f}s to {window.end:.3f}s (part {window.index + 1}).
Main topic: {research.get('title', '')}
Topics: {', '.join(research.get('topics', []))}
Current relevance: {research.get('current_relevance', '')}

REQUIREMENTS:
- Return {max_moments} moments. Fewer only if the excerpt genuinely cannot support that many.
- LENGTH IS MANDATORY: end_time - start_time must be between {min_clip_duration:.0f} and {max_clip_duration:.0f} seconds.
  A single transcript line is far too short. Span as many consecutive lines as it takes,
  typically {min_clip_duration:.0f}-{max_clip_duration:.0f} seconds of dialogue. Check the arithmetic before answering.
- Timestamps are absolute seconds within the full video, copied exactly from the lines below.
- Every moment must lie inside {window.start:.3f}s to {window.end:.3f}s.
- Spread the moments across the whole excerpt, not just its opening. Find one near each of
  these points: {anchors}. Move off a point only if there is nothing worth clipping near it.
- Moments must not overlap each other.
- Start each clip on a hook: a question, a claim, a surprise, or the first line of a story.
- End each clip on a resolution, not mid-sentence.
- Each clip must make sense on its own, without the surrounding video.
- Do not invent content outside the transcript.
- "score" and every value in "scores" is a number from 0 to 1.

Transcript:
{window.text}

JSON schema:
{{"moments":[{{"start_time":0.0,"end_time":0.0,"title":"...","reason":"...","score":0.0,"scores":{{"relevance":0.0,"importance":0.0,"emotional_impact":0.0,"information_value":0.0,"standalone_context":0.0,"social_media_value":0.0,"current_relevance":0.0}},"speakers":["Speaker 1"]}}]}}
"""
        raw_response = None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(2),
                wait=wait_exponential(multiplier=1, min=1, max=5),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    raw_response = await self._text_client.chat([
                        {"role": "system", "content": "You select high-value, factual, standalone video moments. Return valid JSON only."},
                        {"role": "user", "content": prompt},
                    ], temperature=0.2, max_tokens=WINDOW_MAX_OUTPUT_TOKENS,
                        json_mode=True, json_schema=MOMENTS_JSON_SCHEMA)
                    data = self._parse_json(raw_response)
                    break
        except Exception as exc:
            log.warning(
                "LLM highlight detection failed for window %d (%.1fs-%.1fs): %s",
                window.index, window.start, window.end, exc,
                extra={"raw_response": raw_response},
            )
            return None

        moments = data.get("moments")
        if not isinstance(moments, list):
            log.warning(
                "LLM returned no moments array for window %d (%.1fs-%.1fs)",
                window.index, window.start, window.end,
                extra={"raw_response": (raw_response or "")[:500]},
            )
            return []
        return moments

    @staticmethod
    def _distribution_anchors(start: float, end: float, count: int) -> str:
        """Evenly spaced timestamps naming where to look for each moment."""
        if count <= 1 or end <= start:
            return f"{start:.0f}s"
        step = (end - start) / count
        return ", ".join(f"{start + step * (index + 0.5):.0f}s" for index in range(count))

    def _build_candidate(
        self,
        item: dict[str, Any],
        transcript_segments: list[dict[str, Any]],
        window: TranscriptWindow,
        duration: float,
    ) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        try:
            start = min(duration, max(0.0, float(item.get("start_time", 0.0))))
            end = min(duration, max(start, float(item.get("end_time", start))))
        except (TypeError, ValueError):
            log.debug("Skipped LLM moment", extra={"moment": item, "reason": "invalid_timestamps"})
            return None
        if end <= start:
            log.debug("Skipped LLM moment", extra={"moment": item, "reason": "empty_span"})
            return None

        excerpt = " ".join(
            segment.get("text", "")
            for segment in transcript_segments
            if float(segment.get("end", 0.0)) > start and float(segment.get("start", 0.0)) < end
        ).strip()
        speakers = list(dict.fromkeys(
            segment.get("speaker")
            for segment in transcript_segments
            if segment.get("speaker") and float(segment.get("end", 0.0)) > start and float(segment.get("start", 0.0)) < end
        ))
        scores = item.get("scores", {}) if isinstance(item.get("scores"), dict) else {}
        return {
            "start_time": round(start, 3),
            "end_time": round(end, 3),
            "score": self._normalize_score(item.get("score"), default=0.5),
            "title": str(item.get("title", "")),
            "reason": str(item.get("reason", "")),
            "scores": {
                key: self._normalize_score(scores.get(key), default=0.0)
                for key in (
                    "relevance", "importance", "emotional_impact", "information_value",
                    "standalone_context", "social_media_value", "current_relevance",
                )
            },
            "transcript_excerpt": excerpt[:1000],
            "speakers": speakers,
            "reasons": ["llm_selected"],
            "source_window": window.index,
        }

    def _fit_durations(
        self,
        candidates: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]],
        duration: float,
        min_clip_duration: float,
        max_clip_duration: float,
    ) -> list[dict[str, Any]]:
        """Bring every candidate inside the allowed length band.

        A moment shorter than the minimum is grown outward rather than dropped:
        the model is good at spotting where the interesting passage is and bad at
        saying how long it runs, so its start/end are treated as a seed. Bounds
        are then snapped onto word timestamps so cuts land in pauses instead of
        mid-word.
        """
        if duration <= 0:
            return candidates

        # A video shorter than the requested minimum can only ever yield itself.
        floor = min(min_clip_duration, duration)
        ceiling = max(floor, min(max_clip_duration, duration))

        fitted: list[dict[str, Any]] = []
        for candidate in candidates:
            start = max(0.0, float(candidate.get("start_time", 0.0)))
            end = min(duration, float(candidate.get("end_time", start)))
            if end <= start:
                continue

            if end - start > ceiling:
                end = start + ceiling
            if end - start < floor:
                # Grow forward first, keeping the seed's opening line intact,
                # then backwards only if the video ends too soon.
                end = min(duration, start + floor)
                if end - start < floor:
                    start = max(0.0, end - floor)

            start, end = self._snap_boundaries(
                start, end, transcript_segments, duration,
                min_duration=floor, max_duration=ceiling,
            )
            if end - start <= 0:
                continue

            item = dict(candidate)
            item["start_time"] = round(start, 3)
            item["end_time"] = round(end, 3)
            fitted.append(item)

        dropped = len(candidates) - len(fitted)
        if dropped:
            log.info("Duration fitting dropped %d unusable candidate(s)", dropped)
        return fitted

    @staticmethod
    def _select_spread(candidates: list[dict[str, Any]], max_clips: int, duration: float = 0.0) -> list[dict[str, Any]]:
        """Keep the best ``max_clips``, covering the whole video.

        Ranking by score alone clustered the result: candidates that tie (common
        when the transcript fallback is scoring similar windows) are returned in
        timeline order, so the top N were simply the first N and everything past
        the opening minutes went unrepresented. The timeline is instead split
        into as many buckets as there are slots and the best candidate in each
        is taken first, so a long video yields clips from end to end.
        """
        if not candidates or max_clips <= 0:
            return []

        ranked = sorted(candidates, key=lambda c: float(c.get("score", 0.0)), reverse=True)
        if len(ranked) <= max_clips:
            return sorted(ranked, key=lambda c: float(c.get("start_time", 0.0)))

        span_start = min(float(c.get("start_time", 0.0)) for c in candidates)
        span_end = max(float(c.get("end_time", 0.0)) for c in candidates)
        span_end = max(span_end, duration)
        span = max(1e-6, span_end - span_start)
        bucket_size = span / max_clips

        kept: list[dict[str, Any]] = []
        used_buckets: set[int] = set()
        for candidate in ranked:
            if len(kept) >= max_clips:
                break
            offset = float(candidate.get("start_time", 0.0)) - span_start
            bucket = min(max_clips - 1, int(offset / bucket_size))
            if bucket in used_buckets:
                continue
            if any(
                abs(float(candidate.get("start_time", 0.0)) - float(k.get("start_time", 0.0)))
                < MIN_CLIP_SPACING_SECONDS
                for k in kept
            ):
                continue
            used_buckets.add(bucket)
            kept.append(candidate)

        # One clip per bucket is a preference, not a quota: if sparse regions
        # left slots unfilled, spend them on the best of what is left.
        if len(kept) < max_clips:
            kept_ids = {id(c) for c in kept}
            for candidate in ranked:
                if len(kept) >= max_clips:
                    break
                if id(candidate) in kept_ids:
                    continue
                if any(
                    abs(float(candidate.get("start_time", 0.0)) - float(k.get("start_time", 0.0)))
                    < MIN_CLIP_SPACING_SECONDS
                    for k in kept
                ):
                    continue
                kept.append(candidate)
                kept_ids.add(id(candidate))

        return sorted(kept, key=lambda c: float(c.get("start_time", 0.0)))

    @staticmethod
    def _normalize_score(value: Any, default: float = 0.5) -> float:
        """Map a model-supplied score onto 0-1 whatever scale it chose.

        Models answer this prompt on 0-1, 0-10 and 0-100 depending on the run.
        Clamping instead of rescaling turned every 0-10 answer into 1.0 and
        flattened the ranking, so the spread selection had nothing to work with.
        """
        try:
            score = float(value)
        except (TypeError, ValueError):
            return default
        if score < 0:
            return 0.0
        if score <= 1.0:
            return score
        if score <= 10.0:
            return score / 10.0
        return min(1.0, score / 100.0)

    @staticmethod
    def _max_clips(duration: float, max_clips_per_hour: float, explicit: Any = None) -> int:
        """How many clips to keep for a video of this length.

        The per-hour rate is rounded up rather than truncated, so a short video
        still yields a usable set instead of the one or two clips that integer
        truncation produced.
        """
        if explicit:
            try:
                return max(1, int(explicit))
            except (TypeError, ValueError):
                log.debug("Ignoring invalid max_clips setting: %r", explicit)
        if duration <= 0:
            return MIN_CLIPS
        return max(MIN_CLIPS, math.ceil((duration / 3600.0) * max_clips_per_hour))

    @staticmethod
    def _snap_boundaries(
        start: float,
        end: float,
        segments: list[dict],
        duration: float,
        min_duration: float | None = None,
        max_duration: float = MAX_CLIP_DURATION,
    ) -> tuple[float, float]:
        """Move cut points onto word boundaries, falling back to the input."""
        try:
            from content_intelligence.word_snapper import snap_clip_to_words
            return snap_clip_to_words(
                start, end, segments, duration,
                min_duration=min_duration, max_duration=max_duration,
            )
        except Exception as exc:
            log.debug("Word snapping unavailable, keeping raw bounds: %s", exc)
            return start, end

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start:end + 1]
        try:
            value = json.loads(candidate)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _detect_from_transcript(
        self,
        segments: list[dict],
        category: str,
        duration: float,
        min_clip_duration: float = MIN_CLIP_DURATION,
        max_clip_duration: float = MAX_CLIP_DURATION,
    ) -> list[dict]:
        """Propose clips from the transcript alone, without the model.

        This runs whenever LLM detection comes back empty, so it decides what
        the user sees on a bad day and must never collapse the video into one
        clip. It used to group consecutive segments by speaker, which meant a
        video with no diarization — the normal case, since diarization needs an
        HF token — became a single speaker turn spanning the whole video and
        therefore exactly one clip. It now slides a fixed-length window across
        the entire transcript, so coverage is a function of video length rather
        than of whether diarization happened to run.
        """
        usable = [s for s in segments if str(s.get("text", "")).strip()]
        if not usable:
            log.warning("Transcript fallback: no segments with text")
            return []

        target = max(min_clip_duration, min(max_clip_duration, (min_clip_duration + max_clip_duration) / 2.0))
        step = max(5.0, target / 2.0)
        keywords = self._category_keywords(category)

        candidates: list[dict] = []
        cursor = 0
        next_start = float(usable[0].get("start", 0.0))

        while cursor < len(usable):
            # Prefer opening on a sentence boundary so the clip does not begin
            # mid-thought; fall back to the raw window start.
            begin_index = self._sentence_start_index(usable, cursor)
            begin = float(usable[begin_index].get("start", 0.0))
            window_end = begin + target

            text_parts: list[str] = []
            speakers: list[str] = []
            last_end = begin
            index = begin_index
            while index < len(usable) and float(usable[index].get("start", 0.0)) < window_end:
                text_parts.append(str(usable[index].get("text", "")).strip())
                speaker = usable[index].get("speaker")
                if speaker and speaker not in speakers:
                    speakers.append(speaker)
                last_end = max(last_end, float(usable[index].get("end", last_end)))
                index += 1

            text = " ".join(part for part in text_parts if part).strip()
            end = min(last_end, begin + max_clip_duration)
            if duration > 0:
                end = min(end, duration)

            if text and end - begin >= min(min_clip_duration, target):
                candidates.append({
                    "start_time": round(begin, 3),
                    "end_time": round(end, 3),
                    "score": self._transcript_score(text, keywords),
                    "title": "",
                    "reason": "",
                    "scores": {},
                    "transcript_excerpt": text[:1000],
                    "speakers": speakers,
                    "reasons": ["transcript_window"],
                })

            next_start = begin + step
            cursor = self._index_at_or_after(usable, next_start, minimum=begin_index + 1)

        log.info(
            "Transcript fallback produced %d candidate(s) across %.1fs (target=%.0fs, step=%.0fs)",
            len(candidates), duration, target, step,
        )
        return candidates

    @staticmethod
    def _sentence_start_index(segments: list[dict], cursor: int) -> int:
        """First segment at or after ``cursor`` that follows a sentence end."""
        for index in range(cursor, min(cursor + 4, len(segments))):
            if index == 0:
                return index
            previous = str(segments[index - 1].get("text", "")).rstrip()
            if previous.endswith((".", "?", "!")):
                return index
        return cursor

    @staticmethod
    def _index_at_or_after(segments: list[dict], timestamp: float, minimum: int = 0) -> int:
        """Index of the first segment starting at or after ``timestamp``.

        ``minimum`` guarantees forward progress, so the window loop always
        terminates even when many segments share a start time.
        """
        for index in range(minimum, len(segments)):
            if float(segments[index].get("start", 0.0)) >= timestamp:
                return index
        return len(segments)

    def _detect_from_scenes(self, frame_analysis: dict, duration: float, category: str, min_clip_duration: float = MIN_CLIP_DURATION) -> list[dict]:
        candidates = []
        scene_changes = frame_analysis.get("scene_changes", [])
        if not scene_changes:
            log.debug("No scene changes available for highlight detection")
            return candidates

        skipped = 0
        for i in range(len(scene_changes) - 1):
            start = scene_changes[i]
            end = scene_changes[i + 1]
            if end - start < min_clip_duration:
                skipped += 1
                log.debug(
                    "Skipped scene segment",
                    extra={
                        "start": round(start, 2),
                        "end": round(end, 2),
                        "duration": round(end - start, 2),
                        "reason": "below_min_duration",
                    },
                )
                continue
            candidates.append({
                "start_time": start,
                "end_time": end,
                "score": 0.3,
                "transcript_excerpt": "",
                "speakers": [],
                "reasons": ["scene_boundary"],
            })

        log.debug(
            "Scene highlight detection complete",
            extra={
                "scene_count": len(scene_changes),
                "candidates_kept": len(candidates),
                "candidates_skipped": skipped,
            },
        )

        return candidates

    def _merge_overlapping(self, candidates: list[dict], min_duration: float, max_clip_duration: float = MAX_CLIP_DURATION) -> list[dict]:
        if not candidates:
            return []

        candidates.sort(key=lambda c: c.get("start_time", 0))
        merged = []
        current = candidates[0]

        for next_c in candidates[1:]:
            curr_end = current.get("end_time", 0)
            next_start = next_c.get("start_time", 0)
            merged_end = max(curr_end, next_c.get("end_time", 0))
            merged_duration = merged_end - current.get("start_time", 0)
            if next_start <= curr_end and merged_duration <= max_clip_duration:
                log.debug(
                    "Merged overlapping clips",
                    extra={
                        "current_start": round(current.get("start_time", 0), 2),
                        "current_end": round(current.get("end_time", 0), 2),
                        "next_start": round(next_c.get("start_time", 0), 2),
                        "next_end": round(next_c.get("end_time", 0), 2),
                        "merged_end": round(merged_end, 2),
                    },
                )
                current["end_time"] = merged_end
                current["score"] = max(current.get("score", 0), next_c.get("score", 0))
                current["reasons"] = list(set(current.get("reasons", []) + next_c.get("reasons", [])))
            else:
                if current.get("end_time", 0) - current.get("start_time", 0) >= min_duration:
                    merged.append(current)
                else:
                    log.debug(
                        "Skipped merged clip",
                        extra={
                            "start": round(current.get("start_time", 0), 2),
                            "end": round(current.get("end_time", 0), 2),
                            "duration": round(current.get("end_time", 0) - current.get("start_time", 0), 2),
                            "reason": "below_min_duration_after_merge",
                        },
                    )
                current = next_c

        if current.get("end_time", 0) - current.get("start_time", 0) >= min_duration:
            merged.append(current)
        else:
            log.debug(
                "Skipped merged clip",
                extra={
                    "start": round(current.get("start_time", 0), 2),
                    "end": round(current.get("end_time", 0), 2),
                    "duration": round(current.get("end_time", 0) - current.get("start_time", 0), 2),
                    "reason": "below_min_duration_after_merge",
                },
            )

        log.debug(
            "Merge complete",
            extra={
                "input_count": len(candidates),
                "output_count": len(merged),
                "merged_count": len(candidates) - len(merged),
            },
        )

        return merged

    def _transcript_score(self, text: str, keywords: list[str]) -> float:
        """Rank one fallback window, on 0-1.

        Category keywords alone returned a flat 0.2 for every window of an
        unknown-category video, which left the selection step with nothing to
        rank by. Generic engagement signals and speech density are always
        available, so they carry the score when keywords are not.
        """
        if not text:
            return 0.0
        lowered = text.lower()

        keyword_hits = sum(1 for kw in keywords if kw.lower() in lowered)
        keyword_score = min(1.0, keyword_hits / len(keywords)) if keywords else 0.0

        signal_hits = sum(1 for signal in _FALLBACK_ENGAGEMENT_SIGNALS if signal in lowered)
        signal_score = min(1.0, signal_hits / 6.0)

        question_score = 0.15 if "?" in text else 0.0
        # A window that is mostly silence carries less than one that is dense
        # with speech; 600 characters is roughly a talkative 30 seconds.
        density_score = min(1.0, len(text) / 600.0) * 0.25

        return round(min(1.0, 0.1 + keyword_score * 0.35 + signal_score * 0.3 + question_score + density_score), 4)

    def _category_keywords(self, category: str) -> list[str]:
        mapping = {
            "gaming": ["kill", "win", "play", "game", "round", "level", "boss", "match", "victory", "score"],
            "podcast_interview": ["think", "believe", "story", "happen", "experience", "opinion", "question", "answer", "truth", "people"],
            "tutorial_educational": ["step", "learn", "how", "method", "technique", "important", "key", "understand", "practice", "example"],
            "vlog": ["day", "today", "morning", "night", "going", "love", "excited", "new", "home", "friend"],
            "comedy": ["funny", "laugh", "joke", "hilarious", "crazy", "wild", "ridiculous", "silly", "absurd", "meme"],
            "reaction": ["wow", "crazy", "unbelievable", "wait", "what", "no way", "insane", "shocking", "first time"],
            "music": ["song", "lyrics", "beat", "chorus", "verse", "album", "artist", "track", "listen", "music"],
            "news_politics": ["important", "breaking", "report", "official", "statement", "government", "election", "policy", "impact"],
            "tech": ["feature", "update", "launch", "review", "performance", "device", "software", "hardware", "spec", "price"],
            "fitness_health": ["workout", "exercise", "set", "rep", "muscle", "diet", "calorie", "training", "routine", "progress"],
            "food": ["recipe", "taste", "delicious", "cook", "flavor", "ingredient", "kitchen", "fresh", "homemade", "spice"],
            "sports": ["goal", "score", "win", "team", "player", "match", "championship", "season", "record", "play"],
        }
        return mapping.get(category, [])

    def _probe_duration(self, video_path: str) -> float:
        try:
            import subprocess
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip() or 0)
        except Exception:
            return 0.0
