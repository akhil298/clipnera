from __future__ import annotations

import json
import re
from typing import Any

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.logging_config import get_logger

log = get_logger(__name__)


CONTENT_TAXONOMY = [
    "gaming", "podcast_interview", "tutorial_educational", "vlog",
    "comedy", "reaction", "music", "news_politics", "tech",
    "fitness_health", "food", "sports", "unknown",
]

# The category drives framing, hashtags and scoring, so an out-of-taxonomy
# value is a real failure. The enum makes one impossible where enforced.
CLASSIFICATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": list(CONTENT_TAXONOMY)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
    },
    "required": ["category", "confidence", "keywords", "reasoning"],
    "additionalProperties": False,
}

CLASSIFICATION_PROMPT = """You are a content classification assistant. Given a video's title, description, and transcript keywords, determine the most appropriate content category from the following list:
 - gaming
 - podcast_interview
 - tutorial_educational
 - vlog
 - comedy
 - reaction
 - music
 - news_politics
 - tech
 - fitness_health
 - food
 - sports
 - unknown

 Return a JSON object with keys: "category", "confidence" (0-1), "keywords" (list of relevant keywords), "reasoning" (brief explanation).
 Title: {title}
 Description: {description}
 Entities: {entities}
 Events: {events}
 Current relevance: {current_relevance}
 Keywords: {keywords}
 """

class ContentClassifier:
    def __init__(self, text_client: Any) -> None:
        self._text_client = text_client

    async def classify(self, topic_research: dict, transcript_segments: list[dict]) -> dict:
        title = topic_research.get("title", "")
        description = topic_research.get("summary", "")
        keywords = topic_research.get("keywords") or (topic_research.get("topics", []) + topic_research.get("entities", []))
        entities = topic_research.get("entities", [])
        events = topic_research.get("events", [])
        current_relevance = topic_research.get("current_relevance", "")

        prompt = CLASSIFICATION_PROMPT.format(
            title=title,
            description=description,
            entities=", ".join(entities),
            events=", ".join(events),
            current_relevance=current_relevance,
            keywords=", ".join(keywords),
        )

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    response = await self._text_client.chat([
                        {"role": "system", "content": "You are a content classification assistant. Always return valid JSON."},
                        {"role": "user", "content": prompt},
                    ], temperature=0.1, max_tokens=300, json_mode=True, json_schema=CLASSIFICATION_JSON_SCHEMA)
                    result = self._parse_json(response)
                    category = result.get("category", "unknown")
                    if category not in CONTENT_TAXONOMY:
                        category = "unknown"
                    return {
                        "category": category,
                        "confidence": float(result.get("confidence", 0.5)),
                        "keywords": result.get("keywords", keywords),
                        "reasoning": result.get("reasoning", ""),
                    }
        except Exception as exc:
            log.warning(f"Classification failed, falling back to heuristics: {exc}")
            return self._heuristic_classify(title, description, keywords)

    def _heuristic_classify(self, title: str, description: str, keywords: list[str]) -> dict:
        text = f"{title} {description} {' '.join(keywords)}".lower()

        scores = {
            "gaming": len(re.findall(r"\b(game|gaming|playthrough|walkthrough|speedrun|esports|minecraft|fortnite|valorant)\b", text)),
            "podcast_interview": len(re.findall(r"\b(podcast|interview|talk show|conversation|guest|host|episode)\b", text)),
            "tutorial_educational": len(re.findall(r"\b(tutorial|how to|learn|course|education|explain|guide|step by step|lesson)\b", text)),
            "vlog": len(re.findall(r"\b(vlog|day in the life|my day|routine|travel|adventure|life update)\b", text)),
            "comedy": len(re.findall(r"\b(comedy|funny|hilarious|skit|parody|stand up|prank|meme|joke)\b", text)),
            "reaction": len(re.findall(r"\b(reaction|reacting|first time|watching|reviewing|respond)\b", text)),
            "music": len(re.findall(r"\b(song|music|album|artist|lyrics|concert|band|singer|track)\b", text)),
            "news_politics": len(re.findall(r"\b(news|politics|election|government|breaking|analysis|current events|debate)\b", text)),
            "tech": len(re.findall(r"\b(tech|technology|software|hardware|review|unbox|gadget|programming|code|developer|ai)\b", text)),
            "fitness_health": len(re.findall(r"\b(workout|fitness|exercise|gym|health|diet|nutrition|training|yoga)\b", text)),
            "food": len(re.findall(r"\b(recipe|cooking|food|eat|restaurant|kitchen|chef|baking|meal)\b", text)),
            "sports": len(re.findall(r"\b(sports|football|basketball|soccer|nba|nfl|soccer|tennis|highlights|match|game|score)\b", text)),
        }

        best = max(scores, key=scores.get)
        max_score = scores[best]
        total = sum(scores.values()) or 1

        if max_score == 0:
            return {"category": "unknown", "confidence": 0.3, "keywords": keywords, "reasoning": "No strong signals matched"}

        confidence = min(0.95, 0.5 + (max_score / total) * 0.5)
        return {"category": best, "confidence": round(confidence, 2), "keywords": keywords, "reasoning": f"Heuristic match on {best}"}

    def _parse_json(self, text: str) -> dict:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
