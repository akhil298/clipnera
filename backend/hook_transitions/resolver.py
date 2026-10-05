"""Turn a HookTransitionConfig into the concrete transition to render.

Auto mode reads the clip -- its content category and the words of its hook --
and picks a preset and a bridge line that fit. The pick is seeded by the clip
id, so a re-export renders the same transition while a batch of clips still
gets variety instead of one look repeated.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

from hook_transitions.catalog import PHRASES, PRESET_LIST, PRESETS, Preset
from hook_transitions.graphics import pick_graphic
from hook_transitions.schema import HookTransitionConfig

CUSTOM_DEFAULTS = Preset(
    id="custom", name="Custom", group="Custom", source="freeze_frame", effects=(), sound="whoosh",
)

# Content category -> the intent it implies on its own.
_CATEGORY_INTENTS = {
    "gaming": "gaming",
    "sports": "sports",
    "music": "music",
    "food": "food",
    "fitness_health": "fitness",
    "tech": "tech",
    "podcast_interview": "podcast",
    "news_politics": "news",
    "comedy": "funny",
    "reaction": "shock",
    "tutorial_educational": "educational",
    "vlog": "story",
}

# Hook-text cues, strongest first: a hook that asks a question wants an answer
# line more than it wants anything its category suggests.
_TEXT_CUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("question", re.compile(r"\?|^(who|what|why|how|when|where|which|is|are|do|does|did|can|could|would|should)\b")),
    ("money", re.compile(r"[$€£₹]|\b\d[\d,.]*\s*(k|m|percent|%)|\b(millions?|billions?|thousands?|grand|dollars?|bucks|money|rich|salary|profit|revenue|invest\w*|paid|broke|price)\b")),
    ("shock", re.compile(r"\b(never|insane|crazy|shock\w*|unbelievable|impossible|nobody|no one|no way|wtf|omg|died|dead|fired|caught|secret|lied)\b")),
    ("funny", re.compile(r"\b(lol|lmao|haha\w*|funny|joke|hilarious|laugh\w*|weird|dumb|stupid)\b")),
    ("emotional", re.compile(r"\b(love|cried|cry|tears|miss|heart\w*|hurt|scared|afraid|proud|grateful|alone|lost)\b")),
    ("story", re.compile(r"\b(remember|story|years ago|once|back when|when i was|grew up|first time|happened)\b")),
    ("educational", re.compile(r"\b(learn\w*|tip|trick|mistake\w*|step|reason|explain\w*|because|rule|hack|guide|how to)\b")),
    ("hype", re.compile(r"\b(let'?s go|massive|huge|biggest|best|fire|epic|legend\w*|goat)\b")),
)


@dataclass(frozen=True)
class ClipContext:
    """What Auto knows about a clip."""

    clip_id: str
    category: str = "unknown"
    hook_text: str = ""


@dataclass(frozen=True)
class TransitionSpec:
    """A fully resolved bridge, every part named."""

    preset_id: str
    source: str
    effects: tuple[str, ...]
    sound: str
    impact: str
    impact_sound: str | None
    text: str | None
    text_style: str
    duration: float
    # A graphics-library id laid over the bridge, with its sound; None for none.
    graphic: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "source": self.source,
            "effects": list(self.effects),
            "sound": self.sound,
            "impact": self.impact,
            "impact_sound": self.impact_sound,
            "text": self.text,
            "text_style": self.text_style,
            "duration": self.duration,
            "graphic": self.graphic,
        }


def detect_intents(hook_text: str, category: str) -> list[str]:
    """Intents the clip's hook signals, strongest first; always ends in 'general'."""
    text = " ".join(hook_text.lower().split())
    intents = [intent for intent, pattern in _TEXT_CUES if text and pattern.search(text)]
    category_intent = _CATEGORY_INTENTS.get(category)
    if category_intent and category_intent not in intents:
        intents.append(category_intent)
    intents.append("general")
    return intents


def resolve_transition(
    config: HookTransitionConfig | dict[str, Any] | None,
    context: ClipContext,
) -> TransitionSpec | None:
    """The transition to render for one clip, or None when transitions are off.

    ``None`` config means Auto: a clip with a hook always gets a bridge unless
    the user turns it off.
    """
    if config is None:
        config = HookTransitionConfig()
    elif isinstance(config, dict):
        config = HookTransitionConfig.model_validate(config)
    if config.mode == "off":
        return None

    intents = detect_intents(context.hook_text, context.category)
    if config.mode == "auto":
        base = pick_preset(context, intents)
    else:
        base = PRESETS[config.preset_id] if config.preset_id else CUSTOM_DEFAULTS

    return TransitionSpec(
        preset_id=base.id,
        source=config.source or base.source,
        effects=tuple(config.effects) if config.effects is not None else base.effects,
        sound=config.sound or base.sound,
        impact=config.impact or base.impact,
        # "none" arrives as None, so only an explicitly sent field overrides.
        impact_sound=config.impact_sound if "impact_sound" in config.model_fields_set else base.impact_sound,
        text=_bridge_text(config, base, context, intents),
        text_style=config.text_style or base.text_style,
        duration=config.duration or base.duration,
        graphic=None if config.graphic == "none" else (
            config.graphic if config.graphic not in (None, "auto") else pick_graphic(context.clip_id, intents)
        ),
    )


def pick_preset(context: ClipContext, intents: list[str] | None = None) -> Preset:
    """The preset Auto uses for a clip: best fit for its category and hook."""
    intents = intents or detect_intents(context.hook_text, context.category)
    # The hook's strongest intent counts most; "general" barely at all.
    weights = {intent: max(1.0, 2.0 - 0.5 * rank) for rank, intent in enumerate(intents)}
    weights["general"] = 0.5

    def line_fit(preset: Preset) -> float:
        """Whether the preset's bridge line answers this hook.

        Auto is the default look, so it leans towards bridges that say
        something relevant: a line picked to match the hook beats a fixed one,
        and a fixed line that does not fit ("The results" over a memory) is
        never picked.
        """
        if preset.text is None:
            return 0.0
        if preset.text == "auto":
            return 1.5
        return 1.0 if set(PHRASES[preset.text].intents).intersection(intents) else -1.0

    def score(preset: Preset) -> float:
        if preset.fits:
            fit = 2.0 if context.category in preset.fits else -4.0
        else:
            fit = 0.0
        mood = max((weights.get(mood, 0.0) for mood in preset.moods), default=0.0)
        minimal = 1.5 if preset.group == "Minimal" else 0.0
        return fit + mood + line_fit(preset) - minimal

    ranked = sorted(
        (preset for preset in PRESET_LIST if line_fit(preset) >= 0),
        key=score,
        reverse=True,
    )
    best = score(ranked[0])
    # The top tier plus near misses, so a batch of similar clips does not all
    # get one look; sorted, so the pool is always the strongest candidates.
    pool = [preset for preset in ranked if score(preset) >= best - 1.5][:6]
    return pool[_stable_index(context.clip_id, "preset", len(pool))]


def pick_phrase(context: ClipContext, intents: list[str] | None = None) -> str:
    """A bridge line answering the hook's strongest intent that has one."""
    intents = intents or detect_intents(context.hook_text, context.category)
    for intent in intents:
        matches = [phrase for phrase in PHRASES.values() if intent in phrase.intents]
        if matches:
            return matches[_stable_index(context.clip_id, f"text:{intent}", len(matches))].text
    return PHRASES["wait_for_it"].text


def _bridge_text(
    config: HookTransitionConfig, base: Preset, context: ClipContext, intents: list[str],
) -> str | None:
    if config.custom_text:
        return config.custom_text
    choice = config.text_id if config.text_id is not None else base.text
    if choice in (None, "none"):
        return None
    if choice == "auto":
        return pick_phrase(context, intents)
    return PHRASES[choice].text


def _stable_index(seed: str, salt: str, size: int) -> int:
    digest = hashlib.sha1(f"{seed}:{salt}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % max(1, size)


def hook_text_from(transcript: Iterable[dict[str, Any]], start: float, end: float) -> str:
    """The words spoken during ``[start, end)`` of a clip transcript."""
    words: list[str] = []
    for segment in transcript:
        seg_words = segment.get("words") or []
        if seg_words:
            words.extend(
                str(word.get("word", word.get("text", ""))).strip()
                for word in seg_words
                if float(word.get("start", 0.0)) < end and float(word.get("end", 0.0)) > start
            )
        elif float(segment.get("start", 0.0)) < end and float(segment.get("end", 0.0)) > start:
            words.append(str(segment.get("text", "")).strip())
    return " ".join(word for word in words if word)
