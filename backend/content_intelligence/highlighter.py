from __future__ import annotations

import json
import os
import re
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)

MIN_CLIP_DURATION = 20.0
MAX_CLIPS_PER_HOUR = 6.0


class HighlightDetector:
    async def detect(self, video_path: str, transcript_segments: list[dict], analysis: dict) -> list[dict]:
        duration = self._probe_duration(video_path)
        category = analysis.get("classification", {}).get("category", "unknown")
        frame_analysis = analysis.get("frame_analysis", {})

        candidates: list[dict] = []

        if transcript_segments:
            candidates.extend(self._detect_from_transcript(transcript_segments, category))

        candidates.extend(self._detect_from_scenes(frame_analysis, duration, category))

        candidates = self._merge_overlapping(candidates, MIN_CLIP_DURATION)
        max_clips = int((duration / 3600.0) * MAX_CLIPS_PER_HOUR) + 1
        candidates = candidates[:max_clips]

        for i, c in enumerate(candidates):
            c["id"] = f"highlight_{i}"
            c["content_category"] = category

        return candidates

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
