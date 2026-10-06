"""The director: one AI call that decides the whole edit.

It reads a compact footage log (sentences, shots and photos by ID) and answers
with IDs and short strings only: which sentences to keep and in what order,
where B-roll goes, the hook, the pop-ups, the music mood and the look. Code
checks every answer (``validate``) and ``compiler`` turns it into times. When
the call fails, ``fallback_plan`` makes a sensible edit without any AI, so a
reel is never lost to a model error.

Pro runs Sonnet 5; the ``REEL_EDITOR_OPUS`` flag switches Pro to Opus 5.5.
"""

from __future__ import annotations

import json
from typing import Any

from clients.ai import REEL_DIRECTOR_OPUS, get_text_client, openai_only
from core.logging_config import get_logger
from skills import HOOKS, TITLES, skill_block
from edit_engine.looks import DEFAULT_LOOK, LOOKS
from edit_engine.music import MOODS
from edit_engine.story import CONTENT_TYPES

log = get_logger(__name__)

DIRECTOR_VERSION = "2026-09-28.1"
MAX_LOG_SENTENCES = 220
MAX_LOG_SHOTS = 120
OUTPUT_TOKENS = 2500

SYSTEM = """You are a senior short-form video editor making an Instagram Reel from a creator's raw footage. You return valid JSON only, and you refer to footage only by the IDs given (s = sentence, o = voiceover sentence, v = video shot, p = photo).

How great reels are edited:
- The hook lands in the first 1.5 seconds: open on the strongest line, and write a hook headline of at most 6 words that makes people stop scrolling.
- Keep only lines that earn their place. Drop repeats, rambling, greetings like "hi guys", and weak takes. Keep the payoff and end on a line that could loop back to the start.
- Something changes on screen every 2-3 seconds: B-roll, a pop-up or a punch-in.
- B-roll shows the noun being said. Prefer the creator's own shots (v) and photos (p). Never cover the hook line. Use B-roll on at most 40% of lines.
- Pop-ups are 1-3 words (a number, a key word, a price) on a line that deserves emphasis; at most one every 4 seconds.
- Punch-ins (a quick zoom) go on the line where a point lands.
- For footage without speech, "montage" lists the best shots and photos in viewing order: strongest first, varied, no near-duplicates.
- Pick the music mood and energy that fit the content, and a colour look that fits the setting.
- Write the Instagram caption in the creator's language: 1-2 short lines, no hashtags inside; hashtags separately, at most 8.
Follow the creator's intent when given. When the script is marked FIXED, keep every script line in order and only choose visuals, pop-ups, punch-ins, music and look."""

# The reel director reads the editing skills before it plans (backend/skills).
SYSTEM = f"{SYSTEM}\n\n{skill_block(HOOKS, TITLES)}"

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "content_type": {"type": "string", "enum": list(CONTENT_TYPES)},
        "sentences": {"type": "array", "items": {"type": "string"}},
        "broll": {"type": "array", "items": {"type": "object", "properties": {
            "sentence": {"type": "string"}, "visual": {"type": "string"}}, "required": ["sentence", "visual"]}},
        "pops": {"type": "array", "items": {"type": "object", "properties": {
            "sentence": {"type": "string"}, "text": {"type": "string"}}, "required": ["sentence", "text"]}},
        "punch_ins": {"type": "array", "items": {"type": "string"}},
        "montage": {"type": "array", "items": {"type": "string"}},
        "music_mood": {"type": "string", "enum": list(MOODS)},
        "energy": {"type": "string", "enum": ["low", "medium", "high"]},
        "look": {"type": "string", "enum": list(LOOKS)},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "hook", "content_type", "sentences", "broll", "pops", "punch_ins", "montage",
                 "music_mood", "energy", "look", "caption", "hashtags"],
}


def footage_log(analysis: dict[str, Any], mode: str, script: str | None, intent: str | None,
                target_seconds: int, max_seconds: int, fixed: list[str] | None = None) -> str:
    """Everything the director needs, as a few thousand tokens of text."""
    dropped = set(analysis.get("dropped") or [])
    lines = [
        f"CONTENT (detected): {analysis.get('content_type', 'vlog')}",
        f"LANGUAGE: {analysis.get('language', 'en')}",
        f"LENGTH: {'about %d s' % target_seconds if target_seconds else 'you choose, usually 20-45 s'}, never over {max_seconds} s",
    ]
    if intent:
        lines.append(f"CREATOR'S INTENT: {intent}")
    if mode == "spoken" and fixed:
        lines.append("SCRIPT: FIXED. The kept sentences are, in order: " + " ".join(fixed))
    elif mode in ("direction", "onscreen") and script:
        lines.append(f"CREATOR'S NOTES (use as direction, not narration): {script[:1200]}")
    spoken = analysis.get("voice_sentences") if mode == "voiceover" else analysis.get("sentences")
    if spoken:
        lines.append("SENTENCES (id | seconds | text)" + (" -- a voiceover; give every sentence a visual" if mode == "voiceover" else ""))
        for sentence in spoken[:MAX_LOG_SENTENCES]:
            flag = " [weaker take or restart]" if sentence["id"] in dropped else ""
            lines.append(f"{sentence['id']} | {sentence['end'] - sentence['start']:.1f} | {sentence['text'][:200]}{flag}")
    shots = [s for s in analysis.get("shots") or [] if s.get("usable")]
    if shots:
        lines.append("SHOTS (id | file | seconds | shows | face)")
        for shot in shots[:MAX_LOG_SHOTS]:
            lines.append(f"{shot['id']} | f{shot['src']} | {shot['end'] - shot['start']:.1f} | "
                         f"{shot.get('caption') or 'unknown'} | {'face' if shot.get('faces') else '-'}")
    photos = analysis.get("photos") or []
    if photos:
        lines.append("PHOTOS (id | shows)")
        lines += [f"{p['id']} | {p.get('description') or 'photo'}" for p in photos]
    lines.append("Return the JSON edit plan.")
    return "\n".join(lines)


def director_client(is_pro: bool, opus: bool) -> Any:
    # The Opus flag yields to LLM_ROUTING=openai, which sends every step to OpenAI.
    if is_pro and opus and not openai_only():
        return get_text_client(choice=REEL_DIRECTOR_OPUS, step="reel_director")
    return get_text_client(is_pro=is_pro, step="reel_director")


def parse(reply: str) -> dict[str, Any]:
    text = (reply or "").strip()
    start, end = text.find("{"), text.rfind("}")
    try:
        value = json.loads(text[start:end + 1]) if 0 <= start < end else {}
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


async def direct(client: Any, log_text: str) -> dict[str, Any]:
    """The raw plan; an empty dict when the call fails or answers nonsense."""
    try:
        reply = await client.chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": log_text}],
            temperature=0.4, max_tokens=OUTPUT_TOKENS, json_mode=True, json_schema=SCHEMA,
        )
        return parse(reply)
    except Exception as exc:
        log.warning("Director call failed, using the fallback plan: %s", exc)
        return {}


def _short(text: Any, words: int, chars: int) -> str:
    return " ".join(str(text or "").split()[:words])[:chars]


def validate(raw: dict[str, Any], analysis: dict[str, Any], mode: str) -> dict[str, Any]:
    """Keep only what refers to real footage and fits the rules; fill gaps from the fallback."""
    fallback = fallback_plan(analysis, mode)
    sentence_ids = {s["id"] for s in (analysis.get("voice_sentences") if mode == "voiceover" else analysis.get("sentences")) or []}
    visual_ids = {s["id"] for s in analysis.get("shots") or [] if s.get("usable")} | {p["id"] for p in analysis.get("photos") or []}

    def ids(values: Any, allowed: set[str]) -> list[str]:
        seen: list[str] = []
        for value in values if isinstance(values, list) else []:
            if isinstance(value, str) and value in allowed and value not in seen:
                seen.append(value)
        return seen

    sentences = ids(raw.get("sentences"), sentence_ids) or fallback["sentences"]
    broll, covered = [], set()
    for item in raw.get("broll") if isinstance(raw.get("broll"), list) else []:
        if isinstance(item, dict) and item.get("sentence") in sentence_ids and item.get("visual") in visual_ids \
                and item["sentence"] not in covered:
            covered.add(item["sentence"])
            broll.append({"sentence": item["sentence"], "visual": item["visual"]})
    pops = [
        {"sentence": p["sentence"], "text": _short(p.get("text"), 3, 24)}
        for p in (raw.get("pops") if isinstance(raw.get("pops"), list) else [])
        if isinstance(p, dict) and p.get("sentence") in sentence_ids and _short(p.get("text"), 3, 24)
    ]
    hashtags = [("#" + str(h).lstrip("#").replace(" ", ""))[:40] for h in (raw.get("hashtags") or []) if str(h).strip("# ")][:8]
    return {
        "title": _short(raw.get("title"), 12, 80) or fallback["title"],
        "hook": _short(raw.get("hook"), 6, 48) or fallback["hook"],
        "content_type": raw.get("content_type") if raw.get("content_type") in CONTENT_TYPES else analysis.get("content_type", "vlog"),
        "sentences": sentences,
        "broll": broll,
        "pops": pops,
        "punch_ins": ids(raw.get("punch_ins"), sentence_ids),
        "montage": ids(raw.get("montage"), visual_ids) or fallback["montage"],
        "music_mood": raw.get("music_mood") if raw.get("music_mood") in MOODS else fallback["music_mood"],
        "energy": raw.get("energy") if raw.get("energy") in ("low", "medium", "high") else fallback["energy"],
        "look": raw.get("look") if raw.get("look") in LOOKS else DEFAULT_LOOK,
        "caption": str(raw.get("caption") or "").strip()[:600],
        "hashtags": hashtags,
    }


def fallback_plan(analysis: dict[str, Any], mode: str) -> dict[str, Any]:
    """An edit made by rules alone: every good take in order, the usable shots, calm music."""
    dropped = set(analysis.get("dropped") or [])
    spoken = (analysis.get("voice_sentences") if mode == "voiceover" else analysis.get("sentences")) or []
    sentences = [s["id"] for s in spoken if s["id"] not in dropped]
    first = next((s["text"] for s in spoken if s["id"] in sentences), "")
    montage = [s["id"] for s in analysis.get("shots") or [] if s.get("usable")] + [p["id"] for p in analysis.get("photos") or []]
    return {
        "title": _short(first, 8, 80) or "My reel",
        "hook": _short(first, 5, 48),
        "content_type": analysis.get("content_type", "vlog"),
        "sentences": sentences, "broll": [], "pops": [], "punch_ins": [], "montage": montage,
        "music_mood": "chill" if sentences else "upbeat", "energy": "medium", "look": DEFAULT_LOOK,
        "caption": "", "hashtags": [],
    }
