"""The Instagram caption and hashtags posted with each clip.

The burned-in title earns the first second of watch time; this copy earns what
happens after it: searches that find the reel, the line that makes a viewer
open the caption, and the reason to send it to a friend or save it. Clips are
written in batches of a few, all batches at once.

Telugu speech gets Tenglish copy (Telugu in Roman script mixed with English),
never Telugu script; :func:`romanize_text` catches anything the model writes
in Telugu script anyway.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from content_intelligence.director import LANGUAGE_RULE
from content_intelligence.metadata_gen import HASHTAG_POOLS
from core.logging_config import get_logger
from transcription.language import romanize_text

log = get_logger(__name__)

BATCH_CLIPS = 6
EXCERPT_CHARS = 900
MAX_CAPTION_CHARS = 600
# Instagram allows at most five hashtags on a post.
MAX_HASHTAGS = 5
MIN_HASHTAGS = 3
# Tags that describe nothing: they bring no reach and read as spam.
GENERIC_TAGS = frozenset({
    "#fyp", "#foryou", "#foryoupage", "#viral", "#viralvideo", "#viralreels", "#trending", "#trend",
    "#explore", "#explorepage", "#reels", "#reel", "#reelsinstagram", "#instagood", "#instagram",
    "#shorts", "#youtubeshorts", "#tiktok", "#like", "#follow", "#likeforlikes", "#followforfollowback",
})
# Per-language community tags, offered to the model as the one community tag.
LANGUAGE_TAGS = {"te": "#telugu", "hi": "#hindi"}

SYSTEM = "You are the social lead for short-form video creators. You write Instagram Reels captions and hashtags that earn reach honestly. Return valid JSON only."

PLAYBOOK = """How a reel reaches people who do not follow the creator:
- Instagram ranks a reel first on watch time, then on sends (shares by DM), saves, comments and likes per view. Sends are the strongest signal for reaching new people, so give the viewer a reason to send it to someone specific.
- Captions are searchable. Instagram matches them against what people type in search, so name the topic early, in the plain words people search for.
- Only the first line shows before "more", cut at about 125 characters. It must stop the scroll on its own: the tension, promise or surprise of the clip. Do not repeat the burned-in title word for word.
- A post can carry at most 5 hashtags. Use 3-5 specific ones: one for the niche, two or three for the exact topic, and one for the community or language when it fits. Never #fyp, #viral, #explore, #reels, #trending or other tags that describe nothing.
- No clickbait. A caption that promises more than the clip gives makes viewers skip, and the reel is then shown to fewer people.

For each clip return:
- caption: 2-4 short lines joined with \\n. Line 1 is the hook, at most 125 characters. Then a line of context carrying the search words. Then one call to action that fits the clip: a specific question that invites a real answer in the comments, or "send this to the friend who..." / "save this for..." when the clip is advice or a story people pass on. 1-3 emojis in total. No hashtags in the caption. At most 400 characters.
- hashtags: 3-5 tags, each starting with #, no spaces."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "caption": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["index", "caption", "hashtags"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}


class SocialCopyWriter:
    def __init__(self, text_client: Any) -> None:
        self._text_client = text_client

    async def write(self, clips: list[dict], language: str = "en") -> list[dict]:
        """``clips`` with ``social_caption`` and ``hashtags`` set; a failed batch keeps a plain fallback."""
        batches = [list(range(start, min(start + BATCH_CLIPS, len(clips)))) for start in range(0, len(clips), BATCH_CLIPS)]
        written: dict[int, dict] = {}
        for result in await asyncio.gather(*(self._batch(clips, batch, language) for batch in batches), return_exceptions=True):
            if isinstance(result, BaseException):
                log.warning("Social copy batch failed, using the clip's own copy: %s", result)
            else:
                written.update(result)
        return [finish(clip, written.get(index), language) for index, clip in enumerate(clips)]

    async def _batch(self, clips: list[dict], indices: list[int], language: str) -> dict[int, dict]:
        blocks = "\n\n".join(_block(index, clips[index]) for index in indices)
        community = LANGUAGE_TAGS.get(language)
        language_line = f"The speech is {'Telugu' if language == 'te' else 'Hindi'}; {community} is a good community tag." if community else ""
        prompt = f"""{PLAYBOOK}

{LANGUAGE_RULE}
{language_line}

Clips (index, category, burned-in title, transcript):
{blocks}

Return JSON only: {{"items": [{{"index": 0, "caption": "...", "hashtags": ["#..."]}}]}}"""
        reply = await self._text_client.chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.8, max_tokens=320 * len(indices) + 200, json_mode=True, json_schema=SCHEMA,
        )
        data = json.loads(reply[reply.find("{"): reply.rfind("}") + 1] or "{}")
        return {
            item["index"]: item
            for item in data.get("items") or []
            if isinstance(item, dict) and item.get("index") in indices
        }


def _block(index: int, clip: dict) -> str:
    excerpt = " ".join(str(clip.get("transcript_excerpt", "")).split())[:EXCERPT_CHARS]
    return f"[{index}] ({clip.get('content_category', 'unknown')}) title: {clip.get('title', '')}\n{excerpt}"


def finish(clip: dict, copy: dict | None, language: str) -> dict:
    """``clip`` with clean ``social_caption`` and ``hashtags`` (and Tenglish copy for Telugu)."""
    result = dict(clip)
    copy = copy or {}
    caption = str(copy.get("caption") or "").strip()
    if not caption:
        caption = "\n".join(part for part in (clip.get("title"), clip.get("description")) if part)
    tags = clean_hashtags(
        list(copy.get("hashtags") or []) + list(clip.get("hashtags") or []),
        clip.get("content_category", "unknown"), language,
    )
    if language == "te":
        caption = romanize_text(caption)
        for key in ("title", "description"):
            if result.get(key):
                result[key] = romanize_text(str(result[key]))
    result["social_caption"] = caption[:MAX_CAPTION_CHARS].strip()
    result["hashtags"] = tags
    return result


def clean_hashtags(raw: list[Any], category: str, language: str) -> list[str]:
    """3-5 specific, distinct hashtags: the model's first, topped up from the category to 3."""
    tags: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        tag = "#" + re.sub(r"[^\w]", "", romanize_text(str(value)), flags=re.UNICODE)
        if len(tag) >= 3 and tag.lower() not in seen and tag.lower() not in GENERIC_TAGS:
            seen.add(tag.lower())
            tags.append(tag)

    for value in raw:
        if len(tags) == MAX_HASHTAGS:
            break
        add(value)
    pool = ([LANGUAGE_TAGS[language]] if language in LANGUAGE_TAGS else []) + HASHTAG_POOLS.get(category, [])
    for value in pool:
        if len(tags) >= MIN_HASHTAGS:
            break
        add(value)
    return tags
