from __future__ import annotations

import json
import math
import random
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)

CATEGORY_ENGAGEMENT_FACTORS = {
    "gaming": 1.3,
    "comedy": 1.4,
    "reaction": 1.2,
    "music": 1.1,
    "tutorial_educational": 1.0,
    "podcast_interview": 1.1,
    "vlog": 1.0,
    "tech": 1.1,
    "news_politics": 1.05,
    "fitness_health": 1.0,
    "food": 1.0,
    "sports": 1.2,
    "unknown": 0.8,
}

ENGAGEMENT_SIGNALS = [
    "question", "wow", "crazy", "insane", "secret", "hack", "mistake", "fail",
    "win", "best", "worst", "never", "always", "truth", "reveal", "shocking",
    "unbelievable", "story", "secret", "tip", "trick", "hack", "save", "money",
    "free", "easy", "fast", "instant", "guarantee", "proven", "scientifically",
]


class ClipScorer:
    HOOK_SCORE_WEIGHTS = {
        "engagement_signals": 6.0,
        "question_signals": 4.0,
        "urgency_signals": 4.0,
        "curiosity_signals": 5.0,
    }

    ENGAGEMENT_SCORE_WEIGHTS = {
        "emotional_words": 7.0,
        "energy_peaks": 5.0,
        "speaker_turns": 4.0,
        "dialogue_ratio": 4.0,
    }

    VALUE_SCORE_WEIGHTS = {
        "information_density": 8.0,
        "key_fact_signals": 6.0,
        "educational_signals": 6.0,
    }

    SHAREABILITY_SCORE_WEIGHTS = {
        "trending_signals": 7.0,
        "relatability": 6.0,
        "platform_fit": 7.0,
    }

    ENGAGEMENT_SIGNALS = [
        "question", "wow", "crazy", "insane", "secret", "hack", "mistake", "fail",
        "win", "best", "worst", "never", "always", "truth", "reveal", "shocking",
        "unbelievable", "story", "tip", "trick", "save", "money", "free", "easy",
        "fast", "instant", "guarantee", "proven", "scientifically",
    ]

    EMOTIONAL_WORDS = [
        "love", "hate", "amazing", "incredible", "insane", "crazy", "shocking",
        "scary", "funny", "hilarious", "wow", "incredible", "perfect", "hate",
        "beautiful", "ugly", "terrible", "awesome", "brilliant", "stupid",
        "ridiculous", "absurd", "wild", "unbelievable", "disaster", "catastrophe",
    ]

    URGENT_WORDS = [
        "now", "today", "must", "need", "critical", "important", "urgent",
        "breaking", "immediate", "act", "before", "last", "final", "deadline",
    ]

    CURIOSITY_WORDS = [
        "secret", "reveal", "hidden", "unknown", "mystery", "discover",
        "uncover", "surprise", "unexpected", "never", "imagine", "believe",
        "shocking", " unbelievable", "rare", "exclusive", "behind",
    ]

    TRENDING_SIGNALS = [
        "trending", "viral", "fyp", "foryou", "trend", "challenge",
        "hack", "lifehack", "hack", "new", "breaking", "alert",
    ]

    MIN_CLIP_DURATION = 20.0
    MAX_CLIP_DURATION = 60.0
    OPTIMAL_CLIP_DURATION = 32.0

    async def score(self, highlights: list[dict], analysis: dict, clip_settings: dict[str, Any] | None = None) -> list[dict]:
        category = analysis.get("classification", {}).get("category", "unknown")
        engagement_factor = CATEGORY_ENGAGEMENT_FACTORS.get(category, 1.0)
        settings = clip_settings or {}

        min_clip_duration = float(settings.get("min_clip_duration") or self.MIN_CLIP_DURATION)
        max_clip_duration = float(settings.get("max_clip_duration") or self.MAX_CLIP_DURATION)
        optimal_clip_duration = float(settings.get("optimal_clip_duration") or self.OPTIMAL_CLIP_DURATION)

        scored = []
        for h in highlights:
            base_score = h.get("score", 0.3)
            duration = max(0.0, h.get("end_time", 0) - h.get("start_time", 0))
            duration_factor = self._duration_factor(duration, min_clip_duration, optimal_clip_duration, max_clip_duration)
            transcript_excerpt = h.get("transcript_excerpt", "").lower()
            signal_hits = sum(1 for sig in ENGAGEMENT_SIGNALS if sig in transcript_excerpt)
            signal_factor = min(1.0, 0.5 + signal_hits * 0.15)

            reasons = h.get("reasons", [])
            reason_factor = 1.0 + len(reasons) * 0.05

            virality = self._compute_virality_scores(h, transcript_excerpt, duration, category)

            final_score = base_score * engagement_factor * duration_factor * signal_factor * reason_factor
            final_score = min(99.0, max(10.0, final_score * 100))

            h_copy = dict(h)
            h_copy["score"] = round(final_score, 2)
            h_copy["scoring_factors"] = {
                "base": round(base_score, 3),
                "engagement_factor": round(engagement_factor, 2),
                "duration_factor": round(duration_factor, 2),
                "signal_factor": round(signal_factor, 2),
                "reason_factor": round(reason_factor, 2),
                "virality_scores": virality,
            }
            scored.append(h_copy)

        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        return scored

    @classmethod
    def _duration_factor(cls, duration: float, min_duration: float = MIN_CLIP_DURATION, optimal_duration: float = OPTIMAL_CLIP_DURATION, max_duration: float = MAX_CLIP_DURATION) -> float:
        if duration <= min_duration:
            return 0.7
        if duration <= optimal_duration:
            return 0.7 + 0.3 * ((duration - min_duration) / max(1.0, optimal_duration - min_duration))
        if duration <= max_duration:
            return 1.0 - 0.3 * ((duration - optimal_duration) / max(1.0, max_duration - optimal_duration))
        return 0.4

    @classmethod
    def _compute_virality_scores(
        cls,
        highlight: dict,
        text: str,
        duration: float,
        category: str,
    ) -> dict[str, float]:
        hook_score = cls._hook_score(text)
        engagement_score = cls._engagement_score(text, duration)
        value_score = cls._value_score(text, duration)
        shareability_score = cls._shareability_score(text, category)

        total = min(100.0, hook_score + engagement_score + value_score + shareability_score)

        return {
            "hook_score": round(hook_score, 1),
            "engagement_score": round(engagement_score, 1),
            "value_score": round(value_score, 1),
            "shareability_score": round(shareability_score, 1),
            "virality_score": round(total, 1),
        }

    @classmethod
    def _hook_score(cls, text: str) -> float:
        score = 0.0
        for word in cls.ENGAGEMENT_SIGNALS:
            if word in text:
                if word in ("question", "what", "how", "why", "when", "where"):
                    score += cls.HOOK_SCORE_WEIGHTS["question_signals"]
                elif word in ("now", "today", "must", "need"):
                    score += cls.HOOK_SCORE_WEIGHTS["urgency_signals"]
                elif word in cls.CURIOSITY_WORDS:
                    score += cls.HOOK_SCORE_WEIGHTS["curiosity_signals"]
                else:
                    score += cls.HOOK_SCORE_WEIGHTS["engagement_signals"]
        if "?" in text:
            score += cls.HOOK_SCORE_WEIGHTS["question_signals"]
        return min(25.0, score)

    @classmethod
    def _engagement_score(cls, text: str, duration: float) -> float:
        score = 0.0
        emotional_hits = sum(1 for w in cls.EMOTIONAL_WORDS if w in text)
        score += min(7.0, emotional_hits * 2.0)

        word_count = max(1, len(text.split()))
        words_per_second = word_count / max(1.0, duration)
        if 2.0 <= words_per_second <= 6.0:
            score += 5.0
        elif words_per_second > 6.0:
            score += 3.0
        elif words_per_second < 2.0:
            score += 2.0

        if "?" in text or "!" in text:
            score += 2.0

        return min(25.0, score)

    @classmethod
    def _value_score(cls, text: str, duration: float) -> float:
        score = 0.0
        fact_hits = sum(1 for w in ("fact", "data", "statistic", "percentage", "percent", "study", "research", "according") if w in text)
        score += min(6.0, fact_hits * 2.0)

        edu_hits = sum(1 for w in ("how", "step", "learn", "tutorial", "tip", "trick", "method", "technique", "example") if w in text)
        score += min(6.0, edu_hits * 1.5)

        density = len(text) / max(1.0, duration)
        if density > 5.0:
            score += 4.0
        elif density > 2.0:
            score += 2.0

        return min(25.0, score)

    @classmethod
    def _shareability_score(cls, text: str, category: str) -> float:
        score = 0.0
        trending_hits = sum(1 for w in cls.TRENDING_SIGNALS if w in text)
        score += min(7.0, trending_hits * 2.0)

        if any(w in text for w in ("share", "comment", "like", "tag", "follow", "subscribe", "retweet")):
            score += 6.0

        if category in ("comedy", "reaction", "gaming", "music", "sports"):
            score += 4.0

        if len(text) < 200:
            score += 3.0

        return min(25.0, score)


MIN_CLIP_DURATION = 20.0
