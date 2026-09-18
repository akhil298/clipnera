"""The canonical emoji whitelist for captions.

Every emoji that can ever reach a burned caption comes from this file. The LLM
is shown the slug list and must answer with slugs; anything it invents is
dropped by :func:`sanitize_ai_cues` rather than rendered, so a hallucinated
codepoint can never land in a video (and can never hit a font that lacks the
glyph, which is how emoji burn-in usually breaks).

Slugs are stable identifiers - rename one and old stored cues stop resolving.

Keep in step with the frontend mirror:
    cd backend && python -m subtitle_styling.export_emoji_catalog
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class EmojiEntry:
    slug: str
    char: str
    category: str
    keywords: tuple[str, ...]


def _e(slug: str, char: str, category: str, *keywords: str) -> EmojiEntry:
    # The slug is always a keyword for itself, so the LLM answering with a slug
    # that happens to be the spoken word still resolves.
    merged = (slug,) + tuple(k for k in keywords if k != slug)
    return EmojiEntry(slug=slug, char=char, category=category, keywords=merged)


EMOJI_CATALOG: tuple[EmojiEntry, ...] = (
    # --- money ---------------------------------------------------------
    _e("money", "\U0001F4B0", "money", "cash", "fund", "funds", "wealth", "payout"),
    _e("banknote", "\U0001F4B5", "money", "dollar", "dollars", "income", "salary", "paid"),
    _e("money_wings", "\U0001F4B8", "money", "spend", "spending", "sell", "burn_cash", "expense"),
    _e("credit_card", "\U0001F4B3", "money", "debt", "loan", "credit", "subscription"),
    _e("coin", "\U0001FA99", "money", "crypto", "bitcoin", "token", "coins"),
    _e("bank", "\U0001F3E6", "money", "savings", "save", "deposit", "interest"),
    _e("money_face", "\U0001F911", "money", "rich", "millionaire", "billionaire", "profitable"),
    _e("gem", "\U0001F48E", "money", "valuable", "premium", "luxury", "diamond"),
    _e("receipt", "\U0001F9FE", "money", "tax", "taxes", "invoice", "bill"),
    _e("shopping_cart", "\U0001F6D2", "money", "buy", "purchase", "customer", "customers", "sale"),
    _e("price_tag", "\U0001F3F7️", "money", "price", "pricing", "discount", "offer"),
    _e("free", "\U0001F193", "money", "freebie", "no_cost", "zero_cost"),
    # --- growth & results ----------------------------------------------
    _e("chart_up", "\U0001F4C8", "growth", "growth", "grow", "growing", "profit", "revenue", "viral", "increase"),
    _e("chart_down", "\U0001F4C9", "growth", "decline", "drop", "loss", "crash", "decrease"),
    _e("bar_chart", "\U0001F4CA", "growth", "data", "metrics", "analytics", "scale", "invest", "investment", "numbers"),
    _e("trophy", "\U0001F3C6", "growth", "win", "winning", "won", "success", "successful", "champion"),
    _e("medal", "\U0001F947", "growth", "first", "best", "number_one", "winner", "top_spot"),
    _e("target", "\U0001F3AF", "growth", "goal", "goals", "focus", "aim", "precise", "bullseye"),
    _e("check", "✅", "growth", "done", "achieve", "correct", "result", "results", "verified"),
    _e("cross_mark", "❌", "growth", "wrong", "fail", "failure", "mistake", "avoid"),
    _e("arrow_up", "⬆️", "growth", "upgrade", "higher", "raise", "level_up"),
    _e("rocket", "\U0001F680", "growth", "launch", "boost", "startup", "fast_growth", "space", "takeoff"),
    _e("trending", "\U0001F525", "growth", "fire", "hot", "lit", "trending", "blazing"),
    _e("hundred", "\U0001F4AF", "growth", "perfect_score", "hundred_percent", "all_in"),
    # --- mind & learning -----------------------------------------------
    _e("bulb", "\U0001F4A1", "mind", "idea", "ideas", "insight", "answer", "solution", "light", "tip"),
    _e("brain", "\U0001F9E0", "mind", "smart", "genius", "mind", "knowledge", "intelligence", "remember"),
    _e("thinking", "\U0001F914", "mind", "think", "thinking", "consider", "wonder", "hmm"),
    _e("thought_bubble", "\U0001F4AD", "mind", "thought", "imagine", "dream", "reflection"),
    _e("books", "\U0001F4DA", "mind", "learn", "learning", "study", "education", "course"),
    _e("open_book", "\U0001F4D6", "mind", "read", "reading", "book", "lesson", "chapter", "story"),
    _e("graduation", "\U0001F393", "mind", "school", "degree", "graduate", "university", "student"),
    _e("question", "❓", "mind", "ask", "why", "unknown", "confused"),
    _e("exclamation", "❗", "mind", "important", "attention", "alert", "notice"),
    _e("magnifier", "\U0001F50D", "mind", "search", "discover", "find", "look_closer", "investigate"),
    _e("microscope", "\U0001F52C", "mind", "science", "research", "experiment", "analysis"),
    _e("memo", "\U0001F4DD", "mind", "write", "note", "notes", "plan", "list"),
    _e("key", "\U0001F511", "mind", "unlock", "access", "secret_key", "solution_key", "critical"),
    _e("puzzle", "\U0001F9E9", "mind", "piece", "fit", "complex", "solve"),
    # --- emotion --------------------------------------------------------
    _e("mind_blown", "\U0001F92F", "emotion", "insane", "crazy", "incredible", "unbelievable", "shocked"),
    _e("star_struck", "\U0001F929", "emotion", "amazing", "epic", "awesome", "stunning", "wow_good"),
    _e("scream", "\U0001F631", "emotion", "shocking", "scary", "fear", "terrified", "horror"),
    _e("surprised", "\U0001F62E", "emotion", "wow", "surprise", "unexpected", "whoa"),
    _e("smile", "\U0001F604", "emotion", "happy", "happiness", "joy", "glad"),
    _e("laugh", "\U0001F602", "emotion", "funny", "hilarious", "lol", "joke", "comedy"),
    _e("sad", "\U0001F622", "emotion", "sad", "cry", "upset", "unhappy"),
    _e("angry", "\U0001F621", "emotion", "angry", "mad", "rage", "furious"),
    _e("sunglasses", "\U0001F60E", "emotion", "cool", "confident", "smooth", "chill"),
    _e("heart_eyes", "\U0001F60D", "emotion", "beautiful", "gorgeous", "adore", "obsessed"),
    _e("heart", "❤️", "emotion", "love", "loved", "passion", "care"),
    _e("broken_heart", "\U0001F494", "emotion", "heartbreak", "hurt", "breakup", "painful"),
    _e("skull", "\U0001F480", "emotion", "dead", "brutal", "savage", "dying", "cooked"),
    _e("clown", "\U0001F921", "emotion", "foolish", "joke_person", "ridiculous", "embarrassing"),
    _e("sweat", "\U0001F613", "emotion", "stressed", "anxious", "nervous", "pressure"),
    _e("ok_hand", "\U0001F44C", "emotion", "perfect", "nice", "exact", "spot_on"),
    _e("star", "⭐", "emotion", "favorite", "rating", "highlight", "special"),
    _e("sparkles", "✨", "emotion", "magic", "magical", "shine", "new", "fresh"),
    _e("party", "\U0001F389", "emotion", "celebrate", "celebration", "congrats", "launch_party"),
    # --- power & urgency -------------------------------------------------
    _e("muscle", "\U0001F4AA", "power", "strong", "strength", "powerful", "hustle", "grind", "effort", "hard_work"),
    _e("zap", "⚡", "power", "fast", "quick", "quickly", "instantly", "energy", "speed", "power"),
    _e("boom", "\U0001F4A5", "power", "explode", "explosion", "impact", "blow_up", "smash"),
    _e("stop_hand", "✋", "power", "stop", "halt", "wait", "pause", "hold_on"),
    _e("warning", "⚠️", "power", "danger", "caution", "risk", "careful", "beware"),
    _e("bomb", "\U0001F4A3", "power", "ticking", "blow_up_soon", "dangerous", "threat"),
    _e("fist", "\U0001F44A", "power", "punch", "hit", "fight", "force"),
    _e("shield", "\U0001F6E1️", "power", "protect", "protection", "defense", "safe", "secure"),
    _e("lock", "\U0001F512", "power", "locked", "private", "closed", "restricted"),
    _e("unlock", "\U0001F513", "power", "unlocked", "open_access", "revealed"),
    _e("crown", "\U0001F451", "power", "king", "queen", "royal", "elite", "best_in_class"),
    _e("handshake", "\U0001F91D", "power", "deal", "agreement", "partner", "team", "secret", "trust"),
    # --- time -------------------------------------------------------------
    _e("alarm", "⏰", "time", "now", "time", "urgent", "hour", "hours", "wake_up"),
    _e("stopwatch", "⏱️", "time", "minute", "minutes", "second", "seconds", "timer"),
    _e("hourglass", "⏳", "time", "deadline", "running_out", "waiting", "limited_time"),
    _e("calendar", "\U0001F4C5", "time", "today", "tomorrow", "day", "days", "date", "schedule"),
    _e("calendar_year", "\U0001F4C6", "time", "year", "years", "month", "months", "annual"),
    _e("crystal_ball", "\U0001F52E", "time", "future", "predict", "prediction", "forecast"),
    _e("infinity", "♾️", "time", "forever", "unlimited", "endless", "always"),
    _e("repeat", "\U0001F501", "time", "repeat", "loop", "routine", "habit"),
    # --- people ------------------------------------------------------------
    _e("point_right", "\U0001F449", "people", "you", "look_here", "listen"),
    _e("eyes", "\U0001F440", "people", "watch", "watching", "audience", "attention"),
    _e("people", "\U0001F46B", "people", "everyone", "everybody", "crowd", "public"),
    _e("family", "\U0001F468‍\U0001F469‍\U0001F467", "people", "kids", "children", "parents", "home_life"),
    _e("baby", "\U0001F476", "people", "child", "newborn", "beginner", "infant"),
    _e("briefcase", "\U0001F4BC", "people", "work", "working", "job", "business", "career", "boss"),
    _e("office", "\U0001F3E2", "people", "company", "corporate", "enterprise", "firm"),
    _e("bell", "\U0001F514", "people", "subscribe", "notification", "reminder", "alert_bell"),
    _e("mobile", "\U0001F4F2", "people", "followers", "social", "dm", "message", "app"),
    _e("megaphone", "\U0001F4E2", "people", "announce", "shout", "marketing", "promote", "loud"),
    _e("mic", "\U0001F3A4", "people", "speak", "speaking", "podcast", "interview", "voice"),
    _e("clapping", "\U0001F44F", "people", "applause", "well_done", "respect", "praise"),
    _e("thumbs_up", "\U0001F44D", "people", "like", "approve"),
    _e("thumbs_down", "\U0001F44E", "people", "dislike", "disapprove", "reject"),
    _e("wave", "\U0001F44B", "people", "goodbye", "greeting"),
    _e("pray", "\U0001F64F", "people", "thanks", "grateful", "hope"),
    # --- build & make --------------------------------------------------------
    _e("hammer", "\U0001F528", "build", "build", "fix", "repair", "tool"),
    _e("construction", "\U0001F3D7️", "build", "building", "under_construction", "developing", "wip"),
    _e("gear", "⚙️", "build", "system", "process", "settings", "machine", "engine"),
    _e("wrench", "\U0001F527", "build", "adjust", "tune", "maintenance", "configure"),
    _e("art", "\U0001F3A8", "build", "create", "creating", "design", "creative", "paint"),
    _e("brick", "\U0001F9F1", "build", "foundation", "block", "base", "structure"),
    _e("package", "\U0001F4E6", "build", "product", "ship", "shipping", "delivery", "box"),
    _e("toolbox", "\U0001F9F0", "build", "toolkit", "resources", "kit", "equipment"),
    # --- tech ------------------------------------------------------------------
    _e("robot", "\U0001F916", "tech", "ai", "automation", "bot", "machine_learning"),
    _e("laptop", "\U0001F4BB", "tech", "computer", "code", "coding", "software", "tech", "technology"),
    _e("phone", "\U0001F4F1", "tech", "smartphone", "mobile_phone", "device"),
    _e("globe", "\U0001F30D", "tech", "world", "earth", "global", "planet", "international"),
    _e("web", "\U0001F310", "tech", "internet", "online", "website", "network"),
    _e("satellite", "\U0001F4E1", "tech", "signal", "broadcast", "transmit", "connection"),
    _e("battery", "\U0001F50B", "tech", "charge", "energy_level", "power_left", "recharge"),
    _e("floppy", "\U0001F4BE", "tech", "save_file", "backup", "storage", "old_tech"),
    _e("camera", "\U0001F4F7", "tech", "photo", "picture", "shoot", "capture"),
    _e("movie", "\U0001F3AC", "tech", "video", "film", "scene", "production", "clip"),
    _e("tv", "\U0001F4FA", "tech", "television", "broadcast_tv", "show", "channel"),
    _e("game", "\U0001F3AE", "tech", "gaming", "gamer", "controller"),
    _e("music", "\U0001F3B5", "tech", "song", "sound", "audio", "melody"),
    _e("headphones", "\U0001F3A7", "tech", "listen", "listening", "audio_gear", "podcast_listen"),
    # --- health & life ----------------------------------------------------------
    _e("gym", "\U0001F3CB️", "life", "workout", "lifting", "training", "exercise"),
    _e("run", "\U0001F3C3", "life", "running", "sprint", "cardio"),
    _e("food", "\U0001F374", "life", "eat", "eating", "meal", "dinner", "restaurant"),
    _e("apple", "\U0001F34E", "life", "healthy", "nutrition", "diet", "fruit"),
    _e("water", "\U0001F4A7", "life", "hydration", "drink", "liquid", "hydrate"),
    _e("sleep", "\U0001F634", "life", "sleeping", "rest", "tired", "bed"),
    _e("pill", "\U0001F48A", "life", "medicine", "drug", "treatment", "health"),
    _e("hospital", "\U0001F3E5", "life", "doctor", "medical", "clinic", "emergency_room"),
    _e("house", "\U0001F3E0", "life", "home", "property", "real_estate", "living"),
    _e("car", "\U0001F698", "life", "drive", "driving", "vehicle", "commute"),
    _e("plane", "✈️", "life", "travel", "flight", "trip", "vacation"),
    _e("sun", "☀️", "life", "sunny", "morning", "bright", "summer"),
    _e("moon", "\U0001F319", "life", "night", "evening", "late", "dark"),
    _e("seedling", "\U0001F331", "life", "beginning", "small_start", "plant", "nature"),
    _e("tree", "\U0001F333", "life", "nature", "forest", "long_term", "roots"),
    _e("ocean", "\U0001F30A", "life", "sea", "wave", "water_big", "deep"),
    _e("mountain", "⛰️", "life", "climb", "peak", "challenge", "summit"),
    _e("map", "\U0001F5FA️", "life", "roadmap", "direction", "journey", "navigate"),
    _e("compass", "\U0001F9ED", "life", "guidance", "direction_find", "orientation", "north"),
    _e("flag", "\U0001F6A9", "life", "milestone", "marker", "claim", "checkpoint"),
    _e("ticket", "\U0001F3AB", "life", "entry", "pass", "admission", "event"),
    _e("gift", "\U0001F381", "life", "present", "bonus", "reward", "surprise_gift"),
    _e("ball", "⚽", "life", "sports", "soccer", "football", "game_sport"),
)


CATALOG_BY_SLUG: dict[str, EmojiEntry] = {entry.slug: entry for entry in EMOJI_CATALOG}
CATALOG_BY_CHAR: dict[str, EmojiEntry] = {entry.char: entry for entry in EMOJI_CATALOG}

# Variation selector U+FE0F is optional in practice; index the bare form too so
# an LLM (or an older stored cue) that omits it still resolves.
for _entry in EMOJI_CATALOG:
    _bare = _entry.char.replace("️", "")
    CATALOG_BY_CHAR.setdefault(_bare, _entry)

CATEGORIES: tuple[str, ...] = tuple(dict.fromkeys(entry.category for entry in EMOJI_CATALOG))

_NORMALIZE_RE = re.compile(r"[^a-z0-9%]+")


def normalize_keyword(value: str) -> str:
    """Lowercase and strip everything a spoken word would not carry."""
    return _NORMALIZE_RE.sub("", (value or "").lower())


def keyword_emoji_map() -> dict[str, str]:
    """Flatten the catalog into the ``keyword -> emoji char`` lookup.

    Earlier entries win on collision, so the catalog order is the priority
    order: put the more literal sense of a word first.
    """
    lookup: dict[str, str] = {}
    for entry in EMOJI_CATALOG:
        for keyword in entry.keywords:
            normalized = normalize_keyword(keyword)
            if normalized:
                lookup.setdefault(normalized, entry.char)
    return lookup


def resolve_emoji(value: str | None) -> str | None:
    """Resolve a slug *or* a literal emoji to a whitelisted emoji character.

    Anything outside the catalog returns ``None`` - that is the gate that keeps
    model-invented emoji out of rendered captions.
    """
    if not value:
        return None
    raw = str(value).strip()
    if raw in CATALOG_BY_CHAR:
        return CATALOG_BY_CHAR[raw].char
    bare = raw.replace("️", "")
    if bare in CATALOG_BY_CHAR:
        return CATALOG_BY_CHAR[bare].char
    entry = CATALOG_BY_SLUG.get(normalize_keyword(raw).replace(" ", "_"))
    if entry:
        return entry.char
    entry = CATALOG_BY_SLUG.get(raw.lower().replace(" ", "_").replace("-", "_"))
    return entry.char if entry else None


def sanitize_ai_cues(cues: Any, *, max_cues: int = 24) -> list[dict[str, str]]:
    """Coerce raw LLM output into ``[{"keyword", "emoji"}]`` cues we trust.

    Drops cues with an unknown emoji, an empty keyword, or a duplicate keyword.
    """
    if not isinstance(cues, Iterable) or isinstance(cues, (str, bytes)):
        return []

    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        keyword = normalize_keyword(str(cue.get("keyword", "")))
        emoji = resolve_emoji(cue.get("emoji") or cue.get("emoji_id") or cue.get("slug"))
        if not keyword or not emoji or keyword in seen:
            continue
        seen.add(keyword)
        cleaned.append({"keyword": keyword, "emoji": emoji})
        if len(cleaned) >= max_cues:
            break
    return cleaned


def catalog_prompt_block() -> str:
    """Render the whitelist for an LLM prompt, grouped by category.

    Slugs only - the model never has to emit a codepoint, which is what makes
    the output checkable against the catalog.
    """
    by_category: dict[str, list[EmojiEntry]] = {}
    for entry in EMOJI_CATALOG:
        by_category.setdefault(entry.category, []).append(entry)
    return "\n".join(
        f"{category}: " + ", ".join(entry.slug for entry in entries)
        for category, entries in by_category.items()
    )
