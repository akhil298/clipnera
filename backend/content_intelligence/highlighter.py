from __future__ import annotations

import json
import math
from typing import Any

from clients.ai.groq import input_token_budget
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
MAX_CLIPS_PER_HOUR = 12.0

# Output cap per window. Each moment costs roughly 120 tokens of JSON, so this
# comfortably covers the handful of moments we ask any single window for.
WINDOW_MAX_OUTPUT_TOKENS = 1400
# Tokens reserved for the instruction block wrapped around each window.
PROMPT_OVERHEAD_TOKENS = 500


class HighlightDetector:
    def __init__(self, text_client: Any | None = None) -> None:
        self._text_client = text_client

    async def detect(self, video_path: str, transcript_segments: list[dict], analysis: dict, clip_settings: dict[str, Any] | None = None) -> list[dict]:
        duration = self._probe_duration(video_path)
        category = analysis.get("classification", {}).get("category", "unknown")
        settings = clip_settings or {}

        min_clip_duration = float(settings.get("min_clip_duration") or MIN_CLIP_DURATION)
        max_clip_duration = float(settings.get("max_clip_duration") or MAX_CLIP_DURATION)
        max_clips_per_hour = float(settings.get("max_clips_per_hour") or MAX_CLIPS_PER_HOUR)
        max_clips = self._max_clips(duration, max_clips_per_hour, settings.get("max_clips"))

        candidates = await self._detect_with_llm(
            transcript_segments, analysis, duration, category,
            min_clip_duration, max_clip_duration, target_clips=max_clips,
        )
        if not candidates and transcript_segments:
            log.warning("LLM returned no highlights; falling back to transcript-based clip detection")
            candidates = self._detect_from_transcript(transcript_segments, category, min_clip_duration)
            candidates = [self._cap_candidate(c, duration, min_clip_duration, max_clip_duration) for c in candidates]

        if not candidates:
            log.warning("LLM and fallback both returned no highlights; returning empty clip list")
            return []

        explicit_min = "min_clip_duration" in settings
        explicit_max = "max_clip_duration" in settings
        if explicit_min or explicit_max:
            effective_min = min_clip_duration if explicit_min else 0.0
            effective_max = max_clip_duration if explicit_max else 0.0
            candidates = self._enforce_duration_bounds(candidates, duration, effective_min, effective_max)

        candidates = sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)[:max_clips]

        for i, candidate in enumerate(candidates):
            candidate["id"] = f"highlight_{i}"
            candidate["content_category"] = category

        log.info(
            "Highlight detection complete",
            extra={
                "video_duration": round(duration, 2),
                "min_clip_duration": min_clip_duration,
                "max_clip_duration": max_clip_duration,
                "max_clips_per_hour": max_clips_per_hour,
                "selected_clips": len(candidates),
                "source": "llm_only",
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
        budget = input_token_budget(WINDOW_MAX_OUTPUT_TOKENS) - PROMPT_OVERHEAD_TOKENS
        windows = build_transcript_windows(transcript_segments, budget_tokens=budget)
        if not windows:
            log.warning("No usable transcript segments for highlight detection")
            return []

        per_window = allocate_per_window(target_clips, len(windows))
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
        prompt = f"""Select the best standalone short-form video clips from this transcript excerpt. Return only valid JSON as an object with a "moments" array.

Video category: {category}
Full video duration: {duration:.3f} seconds
This excerpt covers {window.start:.3f}s to {window.end:.3f}s (part {window.index + 1}).
Main topic: {research.get('title', '')}
Topics: {', '.join(research.get('topics', []))}
Current relevance: {research.get('current_relevance', '')}

REQUIREMENTS:
- Return at most {max_moments} moments, the strongest ones only.
- Each clip must be between {min_clip_duration:.0f} and {max_clip_duration:.0f} seconds.
- Timestamps are absolute seconds within the full video, copied exactly from the lines below.
- Every moment must lie inside {window.start:.3f}s to {window.end:.3f}s.
- Prefer the strongest hooks, arguments, or emotional moments.
- Each clip must make sense on its own, without the surrounding video.
- Do not invent content outside the transcript.

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
                    ], temperature=0.2, max_tokens=WINDOW_MAX_OUTPUT_TOKENS)
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
            "score": min(1.0, max(0.0, self._score(item.get("score"), default=0.5))),
            "title": str(item.get("title", "")),
            "reason": str(item.get("reason", "")),
            "scores": {
                "relevance": self._score(scores.get("relevance")),
                "importance": self._score(scores.get("importance")),
                "emotional_impact": self._score(scores.get("emotional_impact")),
                "information_value": self._score(scores.get("information_value")),
                "standalone_context": self._score(scores.get("standalone_context")),
                "social_media_value": self._score(scores.get("social_media_value")),
                "current_relevance": self._score(scores.get("current_relevance")),
            },
            "transcript_excerpt": excerpt[:1000],
            "speakers": speakers,
            "reasons": ["llm_selected"],
            "source_window": window.index,
        }

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
            return 3
        return max(3, math.ceil((duration / 3600.0) * max_clips_per_hour))

    @staticmethod
    def _enforce_duration_bounds(candidates: list[dict], duration: float, min_clip_duration: float, max_clip_duration: float) -> list[dict]:
        enforced = []
        for candidate in candidates:
            start = float(candidate.get("start_time", 0.0))
            end = float(candidate.get("end_time", start))
            if min_clip_duration > 0 and end - start < min_clip_duration:
                continue
            if max_clip_duration > 0 and end - start > max_clip_duration:
                candidate = dict(candidate)
                candidate["start_time"] = round(start, 3)
                candidate["end_time"] = round(start + max_clip_duration, 3)
            enforced.append(candidate)
        return enforced

    @staticmethod
    def _score(value: Any, default: float = 0.0) -> float:
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _snap_boundaries(start: float, end: float, segments: list[dict], duration: float) -> tuple[float, float]:
        try:
            from content_intelligence.word_snapper import snap_clip_to_words
            return snap_clip_to_words(start, end, segments, duration)
        except Exception:
            return start, end

    @staticmethod
    def _cap_duration(start: float, end: float, duration: float, min_clip_duration: float = MIN_CLIP_DURATION, max_clip_duration: float = MAX_CLIP_DURATION) -> tuple[float, float]:
        end = min(end, start + max_clip_duration)
        end = min(end, duration)
        start = max(0.0, min(start, end - min_clip_duration))
        return start, end

    def _cap_candidate(self, candidate: dict, duration: float, min_clip_duration: float = MIN_CLIP_DURATION, max_clip_duration: float = MAX_CLIP_DURATION) -> dict:
        start = float(candidate.get("start_time", 0.0))
        end = float(candidate.get("end_time", start))
        capped_start, capped_end = self._cap_duration(start, end, duration, min_clip_duration, max_clip_duration)
        candidate = dict(candidate)
        candidate["start_time"] = round(capped_start, 3)
        candidate["end_time"] = round(capped_end, 3)
        return candidate

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

    def _detect_from_transcript(self, segments: list[dict], category: str, min_clip_duration: float = MIN_CLIP_DURATION) -> list[dict]:
        candidates = []
        speaker_turns: list[dict] = []
        current_speaker = None
        current_start = None
        current_end = None

        for seg in segments:
            speaker = seg.get("speaker") or "Unknown"
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            text = seg.get("text", "").strip()

            if speaker != current_speaker:
                if current_speaker is not None and (current_end - current_start) >= min_clip_duration:
                    speaker_turns.append({
                        "start": current_start,
                        "end": current_end,
                        "speaker": current_speaker,
                        "text": "",
                    })
                else:
                    if current_speaker is not None:
                        log.debug(
                            "Skipped short speaker turn",
                            extra={
                                "speaker": current_speaker,
                                "start": round(current_start, 2),
                                "end": round(current_end, 2),
                                "duration": round(current_end - current_start, 2),
                                "reason": "below_min_duration",
                            },
                        )
                current_speaker = speaker
                current_start = start
                current_end = end
            else:
                current_end = max(current_end, end)

            if current_start is not None:
                current_end = max(current_end, end)

        if current_speaker is not None and current_end - current_start >= min_clip_duration:
            speaker_turns.append({
                "start": current_start,
                "end": current_end,
                "speaker": current_speaker,
                "text": "",
            })
        elif current_speaker is not None:
            log.debug(
                "Skipped short speaker turn",
                extra={
                    "speaker": current_speaker,
                    "start": round(current_start, 2),
                    "end": round(current_end, 2),
                    "duration": round(current_end - current_start, 2),
                    "reason": "below_min_duration",
                },
            )

        keywords = self._category_keywords(category)
        for turn in speaker_turns:
            turn_text = ""
            for seg in segments:
                if turn["start"] <= seg.get("start", 0) < turn["end"]:
                    turn_text += seg.get("text", "") + " "
            turn["text"] = turn_text.strip()
            score = self._transcript_score(turn_text, keywords)
            if score > 0.1:
                candidates.append({
                    "start_time": round(turn["start"], 3),
                    "end_time": round(turn["end"], 3),
                    "score": score,
                    "transcript_excerpt": turn_text[:300],
                    "speakers": [turn["speaker"]],
                    "reasons": ["speaker_turn", "keyword_match"],
                })
            else:
                log.debug(
                    "Skipped speaker turn",
                    extra={
                        "speaker": turn.get("speaker"),
                        "start": round(turn.get("start", 0), 2),
                        "end": round(turn.get("end", 0), 2),
                        "score": round(score, 2),
                        "reason": "low_keyword_score",
                    },
                )

        log.debug(
            "Transcript highlight detection complete",
            extra={
                "speaker_turns_found": len(speaker_turns),
                "candidates_kept": len(candidates),
                "candidates_skipped": len(speaker_turns) - len(candidates),
            },
        )

        return candidates

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
        if not text:
            return 0.0
        text_lower = text.lower()
        matched = sum(1 for kw in keywords if kw.lower() in text_lower)
        if not keywords:
            return 0.2
        return min(1.0, matched / len(keywords))

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
