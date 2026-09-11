from __future__ import annotations

import json
from typing import Any

from core.logging_config import get_logger
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

log = get_logger(__name__)

MIN_CLIP_DURATION = 20.0
MAX_CLIPS_PER_HOUR = 6.0


class HighlightDetector:
    def __init__(self, text_client: Any | None = None) -> None:
        self._text_client = text_client

    async def detect(self, video_path: str, transcript_segments: list[dict], analysis: dict) -> list[dict]:
        duration = self._probe_duration(video_path)
        category = analysis.get("classification", {}).get("category", "unknown")
        frame_analysis = analysis.get("frame_analysis", {})

        if self._text_client and transcript_segments:
            candidates = await self._detect_with_llm(transcript_segments, analysis, duration, category)
            if candidates:
                candidates = self._merge_overlapping(candidates, MIN_CLIP_DURATION)
                max_clips = int((duration / 3600.0) * MAX_CLIPS_PER_HOUR) + 1
                candidates = sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)[:max_clips]
                for i, candidate in enumerate(candidates):
                    candidate["id"] = f"highlight_{i}"
                    candidate["content_category"] = category
                return candidates

        candidates: list[dict] = []
        if transcript_segments:
            candidates.extend(self._detect_from_transcript(transcript_segments, category))
        candidates.extend(self._detect_from_scenes(frame_analysis, duration, category))
        candidates = self._merge_overlapping(candidates, MIN_CLIP_DURATION)
        max_clips = int((duration / 3600.0) * MAX_CLIPS_PER_HOUR) + 1
        candidates = candidates[:max_clips]

        for i, candidate in enumerate(candidates):
            candidate["id"] = f"highlight_{i}"
            candidate["content_category"] = category

        return candidates

    async def _detect_with_llm(
        self,
        transcript_segments: list[dict[str, Any]],
        analysis: dict[str, Any],
        duration: float,
        category: str,
    ) -> list[dict[str, Any]]:
        transcript = "\n".join(
            f"[{float(segment.get('start', 0.0)):.3f}-{float(segment.get('end', 0.0)):.3f}] "
            f"{segment.get('speaker') or 'Unknown speaker'}: {segment.get('text', '')}"
            for segment in transcript_segments
        )
        research = analysis.get("topic_research", {})
        prompt = f"""Select the best standalone video clips from this transcript. Return only valid JSON as an object with a "moments" array.

Video category: {category}
Video duration: {duration:.3f} seconds
Main topic: {research.get('title', '')}
Topics: {', '.join(research.get('topics', []))}
Current relevance: {research.get('current_relevance', '')}

Score each moment for news relevance, importance, emotional impact, information value, standalone context, social-media value, and current relevance. Prefer concise moments between 20 and 90 seconds. Use exact transcript timestamps and do not invent content.

Transcript:
{transcript}

JSON schema:
{{"moments":[{{"start_time":0.0,"end_time":0.0,"title":"...","reason":"...","score":0.0,"scores":{{"relevance":0.0,"importance":0.0,"emotional_impact":0.0,"information_value":0.0,"standalone_context":0.0,"social_media_value":0.0,"current_relevance":0.0}},"speakers":["Speaker 1"]}}]}}
"""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(2),
                wait=wait_exponential(multiplier=1, min=1, max=5),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    response = await self._text_client.chat([
                        {"role": "system", "content": "You select high-value, factual, standalone video moments. Return valid JSON only."},
                        {"role": "user", "content": prompt},
                    ], temperature=0.2, max_tokens=2200)
                    data = self._parse_json(response)
                    break
        except Exception as exc:
            log.warning(f"LLM highlight detection failed: {exc}")
            return []

        candidates = []
        for item in data.get("moments", []) if isinstance(data.get("moments"), list) else []:
            try:
                start = min(duration, max(0.0, float(item.get("start_time", 0.0))))
                end = min(duration, max(start, float(item.get("end_time", start))))
            except (TypeError, ValueError):
                continue
            if end - start < MIN_CLIP_DURATION:
                continue
            snapped_start, snapped_end = self._snap_boundaries(start, end, transcript_segments, duration)
            start, end = snapped_start, snapped_end
            if end - start < MIN_CLIP_DURATION:
                continue
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
            candidates.append({
                "start_time": round(start, 3),
                "end_time": round(end, 3),
                "score": min(1.0, max(0.0, float(item.get("score", 0.5)))),
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
            })
        return candidates

    @staticmethod
    def _score(value: Any) -> float:
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _snap_boundaries(start: float, end: float, segments: list[dict], duration: float) -> tuple[float, float]:
        try:
            from content_intelligence.word_snapper import snap_clip_to_words
            return snap_clip_to_words(start, end, segments, duration)
        except Exception:
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

    def _detect_from_transcript(self, segments: list[dict], category: str) -> list[dict]:
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
                if current_speaker is not None and (current_end - current_start) >= MIN_CLIP_DURATION:
                    speaker_turns.append({
                        "start": current_start,
                        "end": current_end,
                        "speaker": current_speaker,
                        "text": "",
                    })
                current_speaker = speaker
                current_start = start
                current_end = end
            else:
                current_end = max(current_end, end)

            if current_start is not None:
                current_end = max(current_end, end)

        if current_speaker is not None and current_end - current_start >= MIN_CLIP_DURATION:
            speaker_turns.append({
                "start": current_start,
                "end": current_end,
                "speaker": current_speaker,
                "text": "",
            })

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
                    "start_time": turn["start"],
                    "end_time": turn["end"],
                    "score": score,
                    "transcript_excerpt": turn_text[:300],
                    "speakers": [turn["speaker"]],
                    "reasons": ["speaker_turn", "keyword_match"],
                })

        return candidates

    def _detect_from_scenes(self, frame_analysis: dict, duration: float, category: str) -> list[dict]:
        candidates = []
        scene_changes = frame_analysis.get("scene_changes", [])
        if not scene_changes:
            return candidates

        for i in range(len(scene_changes) - 1):
            start = scene_changes[i]
            end = scene_changes[i + 1]
            if end - start < MIN_CLIP_DURATION:
                continue
            candidates.append({
                "start_time": start,
                "end_time": end,
                "score": 0.3,
                "transcript_excerpt": "",
                "speakers": [],
                "reasons": ["scene_boundary"],
            })

        return candidates

    def _merge_overlapping(self, candidates: list[dict], min_duration: float) -> list[dict]:
        if not candidates:
            return []

        candidates.sort(key=lambda c: c.get("start_time", 0))
        merged = []
        current = candidates[0]

        for next_c in candidates[1:]:
            curr_end = current.get("end_time", 0)
            next_start = next_c.get("start_time", 0)
            if next_start <= curr_end and (next_c.get("end_time", 0) - current.get("start_time", 0)) <= 120:
                current["end_time"] = max(curr_end, next_c.get("end_time", 0))
                current["score"] = max(current.get("score", 0), next_c.get("score", 0))
                current["reasons"] = list(set(current.get("reasons", []) + next_c.get("reasons", [])))
            else:
                if current.get("end_time", 0) - current.get("start_time", 0) >= min_duration:
                    merged.append(current)
                current = next_c

        if current.get("end_time", 0) - current.get("start_time", 0) >= min_duration:
            merged.append(current)

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
