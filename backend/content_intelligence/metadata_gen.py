from __future__ import annotations

import json
import random
from typing import Any

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.logging_config import get_logger

log = get_logger(__name__)

HASHTAG_POOLS = {
    "gaming": ["#gaming", "#gamer", "#gameplay", "#gamingclips", "#videogames", "#gamingshorts", "#twitch", "#streamer"],
    "podcast_interview": ["#podcast", "#interview", "#talk", "#podcasts", "#interviewclip", "#conversation", "#podcastclips"],
    "tutorial_educational": ["#tutorial", "#howto", "#learn", "#education", "#tips", "#shorts", "#tutorials", "#knowledge"],
    "vlog": ["#vlog", "#dayinmylife", "#vlogger", "#mylife", "#vlogs", "#lifeupdate", "#vloglife"],
    "comedy": ["#comedy", "#funny", "#funnyvideos", "#laugh", "#meme", "#comedyvideo", "#hilarious", "#jokes"],
    "reaction": ["#reaction", "#react", "#firsttime", "#reactionvideo", "#reacting"],
    "music": ["#music", "#song", "#musicshorts", "#newmusic", "#musicvideo", "#artist", "#playlist"],
    "news_politics": ["#news", "#politics", "#breaking", "#currentevents", "#politicsnews"],
    "tech": ["#tech", "#technology", "#techreview", "#gadgets", "#techshort", "#unboxing", "#innovation"],
    "fitness_health": ["#fitness", "#workout", "#gym", "#health", "#fitspo", "#exercise", "#personaltrainer"],
    "food": ["#food", "#recipe", "#cooking", "#foodie", "#yummy", "#homemade", "#kitchen", "#delicious"],
    "sports": ["#sports", "#sportsclips", "#highlights", "#nba", "#football", "#soccer", "#basketball", "#goal"],
    "unknown": ["#shorts", "#viral", "#trending", "#fyp", "#foryou"],
}

EMOJI_MAP = {
    "gaming": "\ud83c\udfae",
    "podcast_interview": "\ud83c\udfa4",
    "tutorial_educational": "\ud83d\udcda",
    "vlog": "\ud83d\udcf7",
    "comedy": "\ud83d\ude02",
    "reaction": "\ud83d\ude31",
    "music": "\ud83c\udfb5",
    "news_politics": "\ud83c\udf0e",
    "tech": "\ud83d\udcbb",
    "fitness_health": "\ud83d\udcaa",
    "food": "\ud83c\udf73",
    "sports": "\u26bd\ufe0f",
    "unknown": "\ud83c\udf1f",
}


class MetadataGenerator:
    def __init__(self, text_client: Any) -> None:
        self._text_client = text_client

    async def generate_batch(self, clips: list[dict]) -> list[dict]:
        tasks = [self._generate_for_clip(c) for c in clips]
        results = []
        for task in tasks:
            try:
                results.append(await task)
            except Exception as exc:
                log.warning(f"Metadata generation failed for clip: {exc}")
                results.append(self._fallback_metadata(clips[len(results)]))
        return results

    async def _generate_for_clip(self, clip: dict) -> dict:
        excerpt = clip.get("transcript_excerpt", "")[:500]
        category = clip.get("content_category", "unknown")
        score = clip.get("score", 50)

        prompt = f"""Generate a YouTube Shorts title and description for a clip.
 Category: {category}
 Score (out of 100): {score}
 Transcript excerpt: "{excerpt}"

 Requirements:
 - Title: max 60 chars, catchy, high CTR
 - Description: 1-2 sentences, 100-200 chars
 - Hashtags: 3-5 relevant hashtags
 - Return JSON: {{"title": "...", "description": "...", "hashtags": ["..."]}}
 """

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    response = await self._text_client.chat([
                        {"role": "system", "content": "You are a social media expert specializing in YouTube Shorts metadata. Always return valid JSON only."},
                        {"role": "user", "content": prompt},
                    ], temperature=0.7, max_tokens=300)
        except Exception as exc:
            log.warning(f"Metadata generation failed after retries: {exc}")
            return self._fallback_metadata(clip)

        try:
            data = json.loads(self._extract_json(response))
        except Exception:
            data = {}

        clip_copy = dict(clip)
        clip_copy["title"] = data.get("title", self._default_title(clip, category))
        clip_copy["description"] = data.get("description", self._default_description(clip))
        clip_copy["hashtags"] = data.get("hashtags", random.sample(HASHTAG_POOLS.get(category, HASHTAG_POOLS["unknown"]), min(3, len(HASHTAG_POOLS.get(category, HASHTAG_POOLS["unknown"])))))
        clip_copy["suggested_emoji"] = EMOJI_MAP.get(category, "\ud83c\udf1f")
        return clip_copy

    def _fallback_metadata(self, clip: dict) -> dict:
        category = clip.get("content_category", "unknown")
        excerpt = clip.get("transcript_excerpt", "")[:60]
        clip_copy = dict(clip)
        clip_copy["title"] = self._default_title(clip, category)
        clip_copy["description"] = self._default_description(clip)
        clip_copy["hashtags"] = random.sample(HASHTAG_POOLS.get(category, HASHTAG_POOLS["unknown"]), 3)
        clip_copy["suggested_emoji"] = EMOJI_MAP.get(category, "\ud83c\udf1f")
        return clip_copy

    def _default_title(self, clip: dict, category: str) -> str:
        excerpt = clip.get("transcript_excerpt", "")[:40]
        emoji = EMOJI_MAP.get(category, "\ud83c\udf1f")
        return f"{emoji} {excerpt}..."

    def _default_description(self, clip: dict) -> str:
        return clip.get("transcript_excerpt", "")[:150]

    def _extract_json(self, text: str) -> str:
        match = __import__("re").search(r"\{.*\}", text, __import__("re").DOTALL)
        return match.group(0) if match else "{}"
