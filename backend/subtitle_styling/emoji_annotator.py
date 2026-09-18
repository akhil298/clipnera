from __future__ import annotations

import re
from typing import Any

from subtitle_styling.emoji_catalog import (  # noqa: F401  (re-exported)
    catalog_prompt_block,
    keyword_emoji_map,
    normalize_keyword,
    resolve_emoji,
    sanitize_ai_cues,
)

# The catalog in emoji_catalog.py is the single source of truth for which
# emojis may ever be rendered; this is just its flattened keyword index.
EMOJI_KEYWORD_MAP: dict[str, str] = keyword_emoji_map()


POWER_WORDS: set[str] = {
    "never", "always", "everything", "nothing", "everyone", "nobody",
    "anyone", "best", "worst", "most", "biggest", "huge", "massive",
    "tiny", "every", "only", "first", "last", "free", "now", "today",
    "instantly", "forever", "guaranteed", "proven", "secret", "truth",
    "fact", "literally", "actually", "exactly", "must", "need", "stop",
    "warning", "danger", "critical", "key", "important", "remember",
    "mistake", "wrong", "right", "perfect", "ultimate", "powerful",
    "insane", "crazy", "incredible", "amazing", "shocking", "viral",
    "million", "billion", "thousand", "percent", "double", "triple",
    "ten",
}

EMOJI_COLLECTIONS: dict[str, list[str]] = {
    "skull_fire": ["\U0001F480", "\U0001F525"],
    "skull_only": ["\U0001F480"],
    "fire": ["\U0001F525"],
    "fire_skull": ["\U0001F525", "\U0001F480"],
    "arrow": ["\U0001F449", "\U0001F5E1\ufe0f"],
    "money_eyes": ["\U0001F4B0", "\U0001F440"],
    "explosion": ["\U0001F4A5", "\U0001F480", "\U0001F525"],
    "rocket": ["\U0001F680", "\U0001F449"],
    "thumbs_up": ["\U0001F44D", "\U0001F449"],
    "crown": ["\U0001F451", "\U0001F449"],
    "lightning": ["\u26a1", "\U0001F4A1"],
    "sparkles": ["\u2728", "\u2728"],
    "shock": ["\U0001F621", "\U0001F621", "\u26a1"],
    "crown_skull": ["\U0001F451", "\U0001F480", "\U0001F525"],
    "dice": ["\U0001F3B2", "\U0001F480"],
    "fist": ["\U0001F44A", "\U0001F449"],
    "eye_fire": ["\U0001F440", "\U0001F525"],
    "clown": ["\U0001F927", "\U0001F525"],
    "ghost": ["\U0001F47B", "\U0001F480"],
    "skull_crossbones": ["\U0001F480", "\u2620\ufe0f"],
}

_COLLECTION_NAME_ALIASES: dict[str, str] = {
    "skull_fire": "skull_fire",
    "skullfire": "skull_fire",
    "skull and fire": "skull_fire",
    "fire_skull": "fire_skull",
    "fireskull": "fire_skull",
    "fire and skull": "fire_skull",
}


def get_emoji_collection(name: str) -> list[str]:
    """Return the emoji list for a named collection, falling back to skull_fire."""
    if not name:
        return EMOJI_COLLECTIONS["skull_fire"]
    normalized = _COLLECTION_NAME_ALIASES.get(name.lower().strip(), name.lower().strip())
    return EMOJI_COLLECTIONS.get(normalized, EMOJI_COLLECTIONS["skull_fire"])


def inject_collection_emojis(
    text: str,
    collection_name: str | None = None,
    max_insertions: int = 3,
) -> str:
    """Insert collection emojis at natural break points in caption text.

    Places emojis after the first word and before the last word by default,
    producing effects like 'WHY 💀🔥 99% OF CREATORS FAIL'.
    """
    if not collection_name:
        return text
    emojis = get_emoji_collection(collection_name)
    if not emojis:
        return text

    spaces = [i for i, ch in enumerate(text) if ch == " "]
    if len(spaces) < 2:
        insertion = " ".join(emojis[:max_insertions])
        return f"{text} {insertion}"

    first_break = spaces[0] + 1
    last_break = spaces[-1]

    prefix = " ".join(emojis[: max_insertions // 2 + 1]) if emojis else ""
    middle = " ".join(emojis[max_insertions // 2 + 1 : max_insertions]) if len(emojis) > max_insertions // 2 + 1 else ""

    if middle:
        return (
            text[:first_break] + prefix + " " +
            text[first_break:last_break] + " " + middle + " " +
            text[last_break:]
        )
    return text[:first_break] + prefix + " " + text[first_break:]


_NUMBER_RE = re.compile(r"\d")

# Caption tokens and catalog keywords have to normalize identically or a
# lookup silently misses, so this is the catalog's own normalizer.
normalize_token = normalize_keyword


def _singularize(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("es") and not token.endswith("ses"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _lookup_emoji(token: str, lookup: dict[str, str]) -> str | None:
    if not token:
        return None
    if token in lookup:
        return lookup[token]
    singular = _singularize(token)
    if singular != token and singular in lookup:
        return lookup[singular]
    return None


def build_emoji_lookup(ai_cues: list[dict[str, Any]] | None = None) -> dict[str, str]:
    """Keyword lookup = the static catalog index, overridden by per-clip AI cues.

    Cues are re-validated against the catalog here even though the generator
    already sanitized them, because cues are persisted in analysis_json and a
    row written before the catalog changed can still name a dropped emoji.
    """
    lookup = dict(EMOJI_KEYWORD_MAP)
    for cue in sanitize_ai_cues(ai_cues or []):
        lookup[cue["keyword"]] = cue["emoji"]
    return lookup


def annotate_caption_words(
    words: list[dict[str, Any]],
    ai_cues: list[dict[str, Any]] | None = None,
    *,
    enable_emoji: bool = True,
    enable_emphasis: bool = True,
    max_emojis: int = 8,
    min_word_gap: int = 3,
    repeat_gap: int = 8,
) -> tuple[dict[int, str], set[int]]:
    emoji_by_index: dict[int, str] = {}
    emphasis_indices: set[int] = set()
    if not words:
        return emoji_by_index, emphasis_indices

    lookup = build_emoji_lookup(ai_cues) if enable_emoji else {}

    last_emoji_word = -(min_word_gap + 1)
    recent_emoji: dict[str, int] = {}
    emoji_count = 0

    for idx, word in enumerate(words):
        raw = str(word.get("text", ""))
        token = normalize_token(raw)
        if not token:
            continue

        is_number = bool(_NUMBER_RE.search(token))
        emoji = _lookup_emoji(token, lookup) if enable_emoji else None

        if enable_emphasis and (emoji or token in POWER_WORDS or is_number):
            emphasis_indices.add(idx)

        if not emoji or emoji_count >= max_emojis:
            continue
        if idx - last_emoji_word < min_word_gap:
            continue
        if idx - recent_emoji.get(emoji, -(repeat_gap + 1)) < repeat_gap:
            continue

        emoji_by_index[idx] = emoji
        emphasis_indices.add(idx)
        last_emoji_word = idx
        recent_emoji[emoji] = idx
        emoji_count += 1

    return emoji_by_index, emphasis_indices
