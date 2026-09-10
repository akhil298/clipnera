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
    async def score(self, highlights: list[dict], analysis: dict) -> list[dict]:
        category = analysis.get("classification", {}).get("category", "unknown")
        engagement_factor = CATEGORY_ENGAGEMENT_FACTORS.get(category, 1.0)

        scored = []
        for h in highlights:
            base_score = h.get("score", 0.3)
            duration = h.get("end_time", 0) - h.get("start_time", 0)
            duration_factor = min(1.0, (duration - MIN_CLIP_DURATION) / 45.0 + 0.7)
            transcript_excerpt = h.get("transcript_excerpt", "").lower()
            signal_hits = sum(1 for sig in ENGAGEMENT_SIGNALS if sig in transcript_excerpt)
            signal_factor = min(1.0, 0.5 + signal_hits * 0.15)

            reasons = h.get("reasons", [])
            reason_factor = 1.0 + len(reasons) * 0.05

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
            }
            scored.append(h_copy)

        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        return scored


MIN_CLIP_DURATION = 20.0
