from __future__ import annotations

import json
import random
from typing import Any

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.logging_config import get_logger
from subtitle_styling.emoji_catalog import catalog_prompt_block, sanitize_ai_cues

log = get_logger(__name__)

# Enforced where supported. emoji ids are still sanitised afterwards against
# the catalog, since a schema can require a string but not a valid id.
METADATA_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "emoji_cues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "emoji": {"type": "string"},
                },
                "required": ["keyword", "emoji"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "description", "hashtags", "emoji_cues"],
    "additionalProperties": False,
}

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


# The title and description the tier's model writes, and the emoji cues the
# cheap model looks up. Kept apart so the 306-token emoji catalog -- which only
# the cue call needs -- never rides the paid call, and so the highest-volume
# work in the pipeline can sit on the free provider whatever the user pays.
TITLE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "description", "hashtags"],
    "additionalProperties": False,
}

CUES_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "emoji_cues": METADATA_JSON_SCHEMA["properties"]["emoji_cues"],
    },
    "required": ["emoji_cues"],
    "additionalProperties": False,
}


class MetadataGenerator:
    """Writes the headline burned into a clip and the emoji its captions show.

    Two calls per clip rather than one: the title is copywriting and follows the
    user's tier, while the cues are a lookup against a fixed list and always run
    on the cheap provider. Splitting them also keeps the emoji catalog out of
    the title prompt entirely.
    """

    def __init__(self, text_client: Any, cue_client: Any | None = None) -> None:
        self._text_client = text_client
        # Falls back to the same client, so a caller that predates the split
        # still works -- it just pays the tier's price for the cue call too.
        self._cue_client = cue_client or text_client

    async def generate_batch(self, clips: list[dict]) -> list[dict]:
        results = []
        for clip in clips:
            try:
                results.append(await self._generate_for_clip(clip))
            except Exception as exc:
                log.warning(f"Metadata generation failed for clip: {exc}")
                results.append(self._fallback_metadata(clip))
        return results

    async def _generate_for_clip(self, clip: dict) -> dict:
        category = clip.get("content_category", "unknown")
        clip_copy = dict(clip)

        title_data = await self._generate_title(clip, category)
        clip_copy["title"] = title_data.get("title") or self._default_title(clip, category)
        clip_copy["description"] = title_data.get("description") or self._default_description(clip)
        hashtags = title_data.get("hashtags")
        if not hashtags:
            pool = HASHTAG_POOLS.get(category, HASHTAG_POOLS["unknown"])
            hashtags = random.sample(pool, min(3, len(pool)))
        clip_copy["hashtags"] = hashtags
        clip_copy["suggested_emoji"] = EMOJI_MAP.get(category, DEFAULT_EMOJI)

        # Cue failure must not cost the clip its title, so it is caught here
        # rather than failing the whole clip: captions still render from the
        # static keyword map in emoji_annotator.
        try:
            cues = await self._generate_cues(clip)
        except Exception as exc:
            log.warning(f"Emoji cue generation failed, falling back to the static map: {exc}")
            cues = []
        clip_copy["ai_emoji_cues"] = cues
        return clip_copy

    async def _generate_title(self, clip: dict, category: str) -> dict:
        """Headline, description and hashtags. No emoji catalog in this prompt."""
        excerpt = clip.get("transcript_excerpt", "")[:500]
        score = clip.get("score", 50)
        prompt = f"""Generate a YouTube Shorts title and description for a clip.
 Category: {category}
 Score (out of 100): {score}
 Transcript excerpt: "{excerpt}"

 Requirements:
 - Title: ONE short sentence, max 60 chars, catchy, high CTR. It is burned as a
   static headline above the moving captions, so it must read on its own and
   must NOT be a fragment of the transcript.
 - Description: 1-2 sentences, 100-200 chars
 - Hashtags: 3-5 relevant hashtags

 Return JSON only:
 {{"title": "...", "description": "...", "hashtags": ["..."]}}
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
                    ], temperature=0.7, max_tokens=500, json_mode=True, json_schema=TITLE_JSON_SCHEMA)
        except Exception as exc:
            log.warning(f"Title generation failed after retries: {exc}")
            return {}
        try:
            return json.loads(self._extract_json(response))
        except Exception:
            return {}

    async def _generate_cues(self, clip: dict) -> list[dict]:
        """Map spoken words to emoji ids. Always the cheap provider."""
        excerpt = clip.get("transcript_excerpt", "")[:500]
        prompt = f"""Map words spoken in this transcript excerpt to emoji ids.
 Transcript excerpt: "{excerpt}"

 Return 4-10 pairs. Rules, all mandatory:
   * "keyword" must be a single lowercase word from the excerpt, no punctuation.
   * "emoji" must be an id copied EXACTLY from the allowed list below.
     Never invent an id and never output an emoji character.
   * Pick the id whose meaning matches that word; skip the word if none fits.
   * One cue per word, no duplicate keywords.

 Allowed emoji ids (the ONLY permitted values for "emoji"):
{catalog_prompt_block()}

 Return JSON only:
 {{"emoji_cues": [{{"keyword": "...", "emoji": "..."}}]}}
 """
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=1, max=5),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                response = await self._cue_client.chat([
                    {"role": "system", "content": "You map spoken words to emoji ids from a fixed list. Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ], temperature=0.3, max_tokens=500, json_mode=True, json_schema=CUES_JSON_SCHEMA)
        try:
            data = json.loads(self._extract_json(response))
        except Exception:
            return []
        # Anything the model invented is dropped here rather than rendered, so
        # the burner only ever sees emojis that exist in the catalog.
        return sanitize_ai_cues(data.get("emoji_cues"))


    def _fallback_metadata(self, clip: dict) -> dict:
        category = clip.get("content_category", "unknown")
        excerpt = clip.get("transcript_excerpt", "")[:60]
        clip_copy = dict(clip)
        clip_copy["title"] = self._default_title(clip, category)
        clip_copy["description"] = self._default_description(clip)
        clip_copy["hashtags"] = random.sample(HASHTAG_POOLS.get(category, HASHTAG_POOLS["unknown"]), 3)
        clip_copy["suggested_emoji"] = EMOJI_MAP.get(category, "\ud83c\udf1f")
        # No cues: the static keyword map in emoji_annotator still applies.
        clip_copy["ai_emoji_cues"] = []
        return clip_copy

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
