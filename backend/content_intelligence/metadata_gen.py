from __future__ import annotations

import json
import random
from typing import Any

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from content_intelligence.director import LANGUAGE_RULE
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


DEFAULT_EMOJI = "\ud83c\udf1f"


TITLE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "index": {"type": "integer"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["index", "title", "description", "hashtags"],
    "additionalProperties": False,
}

METADATA_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": TITLE_JSON_SCHEMA}},
    "required": ["items"],
    "additionalProperties": False,
}

# Characters of each clip's transcript shown to the model. Enough to reach the
# payoff of a 60-second clip, which is what a good headline is about.
EXCERPT_CHARS = 1200


class MetadataGenerator:
    """Writes the headline burned into each clip, its description and hashtags.

    One call covers every clip that still needs copy: clips the director already
    titled are left alone, and emoji come from the caption catalog's keyword
    map at render time rather than from a model.
    """

    def __init__(self, text_client: Any) -> None:
        self._text_client = text_client

    async def generate_batch(self, clips: list[dict]) -> list[dict]:
        pending = [index for index, clip in enumerate(clips) if not clip.get("title")]
        written: dict[int, dict] = {}
        if pending:
            try:
                written = await self._generate_titles([clips[index] for index in pending])
            except Exception as exc:
                log.warning(f"Title generation failed, using transcript titles: {exc}")
        return [
            self._finish(clip, written.get(pending.index(index)) if index in pending else None)
            for index, clip in enumerate(clips)
        ]

    def _finish(self, clip: dict, copy: dict | None) -> dict:
        category = clip.get("content_category", "unknown")
        result = dict(clip)
        copy = copy or {}
        result["title"] = clip.get("title") or copy.get("title") or self._default_title(clip, category)
        result["description"] = clip.get("description") or copy.get("description") or self._default_description(clip)
        hashtags = clip.get("hashtags") or copy.get("hashtags")
        if not hashtags:
            pool = HASHTAG_POOLS.get(category, HASHTAG_POOLS["unknown"])
            hashtags = random.sample(pool, min(3, len(pool)))
        result["hashtags"] = hashtags
        result["suggested_emoji"] = EMOJI_MAP.get(category, DEFAULT_EMOJI)
        result.setdefault("ai_emoji_cues", [])
        return result

    async def _generate_titles(self, clips: list[dict]) -> dict[int, dict]:
        """Copy for every clip in one request, keyed by its position in ``clips``."""
        blocks = "\n\n".join(
            f"[{index}] ({clip.get('content_category', 'unknown')}) "
            f"{' '.join(str(clip.get('transcript_excerpt', '')).split())[:EXCERPT_CHARS]}"
            for index, clip in enumerate(clips)
        )
        prompt = f"""Write YouTube Shorts copy for each clip below. Each clip is its index, category and transcript.

For every clip return:
- title: one sentence, at most 60 characters, about the clip's payoff (the answer, reveal or punchline), not its setup. It is burned above the captions, so it must read on its own and must not quote the transcript.
- description: 1-2 sentences, 100-200 characters.
- hashtags: 3-5 relevant hashtags.

{LANGUAGE_RULE}

Clips:
{blocks}

Return JSON only: {{"items": [{{"index": 0, "title": "...", "description": "...", "hashtags": ["#..."]}}]}}"""
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                response = await self._text_client.chat([
                    {"role": "system", "content": "You write short-form video titles that earn the click honestly. Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ], temperature=0.7, max_tokens=120 * len(clips) + 200, json_mode=True, json_schema=METADATA_JSON_SCHEMA)
        data = json.loads(self._extract_json(response))
        return {
            int(item["index"]): item
            for item in data.get("items", [])
            if isinstance(item, dict) and isinstance(item.get("index"), int) and 0 <= item["index"] < len(clips)
        }

    def _default_title(self, clip: dict, category: str) -> str:
        """Title used when the model could not supply one.

        Cuts on a word boundary and prefers the excerpt's first sentence, so a
        failed generation reads as a headline rather than a severed fragment.
        """
        excerpt = " ".join(str(clip.get("transcript_excerpt", "")).split())
        emoji = EMOJI_MAP.get(category, "\ud83c\udf1f")
        if not excerpt:
            return f"{emoji} Untitled clip"

        for terminator in (". ", "? ", "! "):
            head, sep, _ = excerpt.partition(terminator)
            if sep and len(head) <= 60:
                return f"{emoji} {head.strip()}{sep.strip()}"

        if len(excerpt) <= 60:
            return f"{emoji} {excerpt}"
        clipped = excerpt[:60].rsplit(" ", 1)[0].rstrip(",;:- ")
        return f"{emoji} {clipped}..."

    def _default_description(self, clip: dict) -> str:
        return clip.get("transcript_excerpt", "")[:150]

    def _extract_json(self, text: str) -> str:
        match = __import__("re").search(r"\{.*\}", text, __import__("re").DOTALL)
        return match.group(0) if match else "{}"
