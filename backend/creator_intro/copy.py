"""Turning what a creator says about their channel into the intro's words.

One prompt serves every creator, whatever the platform (YouTube, TikTok,
Twitch...), the niche (gaming, travel, finance...) or the language: it gets
the facts the creator typed and returns the one line that says what the channel
is, plus the page style that suits it. Anything unreadable falls back to the
creator's own words, so the intro never waits on the model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.logging_config import get_logger
from creator_intro.platforms import PLATFORM_NAMES

log = get_logger(__name__)

TAGLINE_MAX = 90

SYSTEM = """You write the words for a creator's channel intro: a short clip that plays before \
their videos showing their name, ONE line about the channel, and the platform's follow button.

You get the platform, the niche (may be blank), the channel name and whatever the creator wrote \
about their channel (keywords, a bio, a messy description, any language).

Write the line a new viewer reads in two seconds to know what they will get:
- At most 80 characters. One line, no line breaks.
- Say what the channel is about and what viewers get, in concrete words from the creator's own \
input (the games, places, topics, format). No generic filler like "amazing content" or "welcome".
- Only facts the creator gave. Never invent numbers, awards, schedules, names or claims.
- No hashtags, no emojis, no @handles, no quotes, and do not repeat the channel name.
- Write in the language the creator wrote in; keep names and proper nouns as they wrote them.
- Match the niche's voice: gaming and sports can be punchy, education and finance clear, \
lifestyle and travel warm.

Also pick the page style:
- "dark" suits gaming, tech, music, film, nightlife, esports and streaming.
- "light" suits everything else (travel, food, education, lifestyle, business, kids, vlogs).

Return JSON only: {"tagline": "...", "theme": "light" | "dark"}"""


@dataclass(frozen=True)
class IntroCopy:
    tagline: str
    theme: str


def user_prompt(platform: str, niche: str | None, name: str, about: str) -> str:
    return (
        f"Platform: {PLATFORM_NAMES.get(platform, platform)}\n"
        f"Niche: {niche or '(not given)'}\n"
        f"Channel name: {name}\n"
        f"About the channel, in the creator's words:\n{about.strip() or '(nothing given)'}"
    )


def clean_tagline(text: str) -> str:
    """One trimmed line, cut at a word boundary if it runs long."""
    line = " ".join(text.replace("\n", " ").split()).strip().strip('"“”')
    if len(line) <= TAGLINE_MAX:
        return line
    cut = line[:TAGLINE_MAX].rsplit(" ", 1)[0].rstrip(",;:—-")
    return f"{cut}…"


def fallback(about: str, niche: str | None) -> IntroCopy:
    first = about.strip().split("\n")[0].split(". ")[0]
    return IntroCopy(clean_tagline(first or niche or ""), "light")


def parse(response: str, about: str, niche: str | None) -> IntroCopy:
    try:
        data: dict[str, Any] = json.loads(response[response.find("{"): response.rfind("}") + 1])
        tagline = clean_tagline(str(data.get("tagline", "")))
        theme = data.get("theme") if data.get("theme") in ("light", "dark") else "light"
        if tagline:
            return IntroCopy(tagline, theme)
    except (ValueError, TypeError) as exc:
        log.warning("Intro copy was not JSON, using the creator's words: %s", exc)
    return fallback(about, niche)


async def write_copy(client: Any, platform: str, niche: str | None, name: str, about: str) -> IntroCopy:
    try:
        response = await client.chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt(platform, niche, name, about)}],
            temperature=0.5, max_tokens=200, json_mode=True,
        )
    except Exception as exc:
        log.warning("Intro copy failed, using the creator's words: %s", exc)
        return fallback(about, niche)
    return parse(response, about, niche)
