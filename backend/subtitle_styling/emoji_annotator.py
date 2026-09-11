from __future__ import annotations

import re
from typing import Any

EMOJI_KEYWORD_MAP: dict[str, str] = {
    "money": "\U0001F4B0", "cash": "\U0001F4B5", "dollar": "\U0001F4B5",
    "dollars": "\U0001F4B5", "rich": "\U0001F911", "wealth": "\U0001F4B0",
    "wealthy": "\U0001F4B0", "millionaire": "\U0001F911", "billionaire": "\U0001F911",
    "million": "\U0001F4B0", "billion": "\U0001F4B0", "profit": "\U0001F4C8",
    "revenue": "\U0001F4C8", "income": "\U0001F4B5", "salary": "\U0001F4B8",
    "price": "\U0001F3F7\ufe0f", "cost": "\U0001F4B2", "free": "\U0001F193",
    "invest": "\U0001F4CA", "investment": "\U0001F4CA", "investing": "\U0001F4CA",
    "stock": "\U0001F4C8", "stocks": "\U0001F4C8", "crypto": "\U0001FA99",
    "bitcoin": "\u20A7", "business": "\U0001F4BC", "company": "\U0001F3E2",
    "startup": "\U0001F680", "deal": "\U0001F91D", "sale": "\U0001F6D2",
    "buy": "\U0001F6D2", "sell": "\U0001F4B8", "bank": "\U0001F3E2",
    "tax": "\U0001F9FE", "taxes": "\U0001F9FE", "budget": "\U0001F4D2",
    "save": "\U0001F3E6", "savings": "\U0001F3E6", "debt": "\U0001F4B3",
    "fund": "\U0001F4B0",
    "growth": "\U0001F4C8", "grow": "\U0001F4C8", "growing": "\U0001F4C8",
    "scale": "\U0001F4CA", "success": "\U0001F3C6", "successful": "\U0001F3C6",
    "win": "\U0001F3C6", "winning": "\U0001F3C6", "winner": "\U0001F947",
    "won": "\U0001F3C6", "goal": "\U0001F3AF", "goals": "\U0001F3AF",
    "target": "\U0001F3AF", "achieve": "\u2705", "result": "\u2705",
    "results": "\u2705", "best": "\U0001F947", "first": "\U0001F947",
    "top": "\u2b06\ufe0f", "champion": "\U0001F3C6", "level": "\U0001F194",
    "upgrade": "\u2b06\ufe0f", "boost": "\U0001F680", "rocket": "\U0001F680",
    "idea": "\U0001F4A1", "ideas": "\U0001F4A1", "think": "\U0001F914",
    "thinking": "\U0001F914", "thought": "\U0001F4AD", "smart": "\U0001F9E0",
    "genius": "\U0001F9E0", "brain": "\U0001F9E0", "mind": "\U0001F9E0",
    "learn": "\U0001F4DA", "learning": "\U0001F4DA", "study": "\U0001F4DA",
    "school": "\U0001F393", "knowledge": "\U0001F9E0", "lesson": "\U0001F4D6",
    "book": "\U0001F4D6", "books": "\U0001F4DA", "read": "\U0001F4D6",
    "question": "\u2753", "answer": "\U0001F4A1", "secret": "\U0001F91D",
    "truth": "\U0001F499", "fact": "\U0001F4C8", "facts": "\U0001F499",
    "remember": "\U0001F9E0", "focus": "\U0001F3AF", "discover": "\U0001F50D",
    "research": "\U0001F52C",
    "love": "\u2764\ufe0f", "loved": "\u2764\ufe0f", "heart": "\u2764\ufe0f",
    "amazing": "\U0001F929", "incredible": "\U0001F92F", "insane": "\U0001F92F",
    "crazy": "\U0001F92F", "wow": "\U0001F62E", "shocking": "\U0001F631",
    "scary": "\U0001F631", "fear": "\U0001F631", "happy": "\U0001F604",
    "happiness": "\U0001F604", "sad": "\U0001F622", "angry": "\U0001F621",
    "fire": "\U0001F525", "hot": "\U0001F525", "lit": "\U0001F525",
    "cool": "\U0001F60E", "perfect": "\U0001F44C", "beautiful": "\U0001F60D",
    "favorite": "\u2B50", "epic": "\U0001F929", "magic": "\u2728",
    "powerful": "\U0001F4AA", "power": "\u26a1", "strong": "\U0001F4AA",
    "energy": "\u26a1", "stop": "\u270B", "warning": "\u26a0\ufe0f",
    "danger": "\u26a0\ufe0f", "boom": "\U0001F4A5", "explode": "\U0001F4A5",
    "time": "\u23F0", "today": "\U0001F4C5", "tomorrow": "\U0001F4C5",
    "now": "\u23F0", "fast": "\u26a1", "quick": "\u26a1",
    "quickly": "\u26a1", "instantly": "\u26a1", "minute": "\u23F1\ufe0f",
    "minutes": "\u23F1\ufe0f", "hour": "\u23F0", "hours": "\u23F0",
    "day": "\U0001F4C5", "days": "\U0001F4C5", "year": "\U0001F4C6",
    "years": "\U0001F4C6", "future": "\U0001F52E", "forever": "\u267e\ufe0f",
    "deadline": "\u23F3",
    "people": "\U0001F46B", "team": "\U0001F91D", "family": "\U0001F468\u200D\U0001F469\u200D\U0001F467",
    "friend": "\U0001F94E", "friends": "\U0001F94E", "everyone": "\U0001F64C",
    "everybody": "\U0001F64C", "you": "\U0001F449", "audience": "\U0001F440",
    "followers": "\U0001F4F2", "subscribe": "\U0001F514", "viral": "\U0001F4C8",
    "famous": "\U0001F31F", "customer": "\U0001F6D2", "customers": "\U0001F6D2",
    "boss": "\U0001F4BC", "leader": "\U0001FAE1",
    "work": "\U0001F4BC", "working": "\U0001F4BC", "hustle": "\U0001F4AA",
    "grind": "\U0001F4AA", "effort": "\U0001F4AA", "hard": "\U0001F4AA",
    "build": "\U0001F9F2", "building": "\U0001F3D7\ufe0f", "create": "\U0001F3A8",
    "creating": "\U0001F3A8", "health": "\U0001F393", "healthy": "\U0001F973",
    "food": "\U0001F374", "eat": "\U0001F374", "gym": "\U0001F3CB\ufe0f",
    "workout": "\U0001F3CB\ufe0f", "muscle": "\U0001F4AA", "sleep": "\U0001F634",
    "water": "\U0001F4A7", "run": "\U0001F3C3", "running": "\U0001F3C3",
    "ai": "\U0001F916", "robot": "\U0001F916", "tech": "\U0001F4BB",
    "technology": "\U0001F4BB", "computer": "\U0001F4BB", "phone": "\U0001F4F1",
    "internet": "\U0001F310", "online": "\U0001F310", "data": "\U0001F4CA",
    "code": "\U0001F4BB", "world": "\U0001F30D", "earth": "\U0001F30D",
    "global": "\U0001F30D", "space": "\U0001F680", "science": "\U0001F52C",
    "game": "\U0001F3AE", "games": "\U0001F3AE", "music": "\U0001F3B5",
    "video": "\U0001F3AC", "movie": "\U0001F3AC", "car": "\U0001F698",
    "house": "\U0001F3E0", "home": "\U0001F3E0", "travel": "\u2708\ufe0f",
    "light": "\U0001F4A1", "key": "\U0001F511",
}

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

_NORMALIZE_RE = re.compile(r"[^a-z0-9%]+")
_NUMBER_RE = re.compile(r"\d")


def normalize_token(text: str) -> str:
    return _NORMALIZE_RE.sub("", (text or "").lower())


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
    lookup = dict(EMOJI_KEYWORD_MAP)
    for cue in ai_cues or []:
        try:
            keyword = normalize_token(str(cue.get("keyword", "")))
            emoji = str(cue.get("emoji", "")).strip()
        except AttributeError:
            continue
        if keyword and emoji:
            lookup[keyword] = emoji
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
