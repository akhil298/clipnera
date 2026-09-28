from dataclasses import dataclass

from core.config import get_settings
from core.logging_config import get_logger

from .base import BaseAI
from .openai import OpenAI
from .anthropic import Anthropic
from .xai import XAI
from .groq import Groq

log = get_logger(__name__)

Registry = dict[str, type[BaseAI]]

_REGISTRY: Registry = {
    "openai": OpenAI,
    "anthropic": Anthropic,
    "xai": XAI,
    "groq": Groq,
}

# Providers whose clients honour the pipeline's text-client contract: a
# ``chat()`` that accepts ``max_tokens`` / ``json_mode`` / ``json_schema`` and an
# ``input_token_budget()`` the transcript windower sizes itself against. Adding
# a provider here without those means the content-intelligence steps break.
TEXT_PROVIDERS: Registry = {
    "groq": Groq,
    "anthropic": Anthropic,
}

DEFAULT_TEXT_PROVIDER = "groq"

PRO_TEXT_PROVIDER = "anthropic"
FREE_TEXT_PROVIDER = "groq"


@dataclass(frozen=True)
class ModelChoice:
    """Provider, model and (Anthropic only) effort for one step of one tier."""

    provider: str
    model: str
    effort: str | None = None


GROQ_SMALL = ModelChoice("groq", "openai/gpt-oss-20b")
GROQ_LARGE = ModelChoice("groq", "openai/gpt-oss-120b")
SONNET_LOW = ModelChoice("anthropic", "claude-sonnet-5", "low")
SONNET_MEDIUM = ModelChoice("anthropic", "claude-sonnet-5", "medium")
OPUS_MEDIUM = ModelChoice("anthropic", "claude-opus-5-5", "medium")

# (free, pro) per step. Pro pays for judgement only where it decides what the
# viewer sees -- picking and editing the moments. Reading the video, naming it
# and writing copy run on a cheaper model at low effort, and the free tier runs
# entirely on Groq. Most of the old bill was hidden thinking at high effort on
# every call, so effort matters as much as the model here.
STEP_MODELS: dict[str, tuple[ModelChoice, ModelChoice]] = {
    "classification": (GROQ_SMALL, GROQ_SMALL),
    "topic_research": (GROQ_SMALL, SONNET_LOW),
    "map": (GROQ_SMALL, SONNET_LOW),
    "highlight_detection": (GROQ_LARGE, OPUS_MEDIUM),
    "director": (GROQ_LARGE, OPUS_MEDIUM),
    "titles": (GROQ_SMALL, SONNET_LOW),
    # Spelling words in Roman script needs no judgement; the large open model is plenty.
    "transliteration": (GROQ_SMALL, GROQ_LARGE),
    # Where to cut away and what to search for: editorial, but low stakes per call.
    "broll_planning": (GROQ_LARGE, SONNET_LOW),
    # Footage reels: one call decides the whole edit. Pro runs Sonnet by default;
    # the reel editor's Opus flag swaps in REEL_DIRECTOR_OPUS (see edit_engine.director).
    "reel_director": (GROQ_LARGE, SONNET_MEDIUM),
    # Turning a chat message into a few timeline edits needs little judgement.
    "reel_chat": (GROQ_SMALL, SONNET_LOW),
    # Captions for a contact sheet of shots, and the Instagram caption.
    "reel_copy": (GROQ_SMALL, SONNET_LOW),
}

REEL_DIRECTOR_OPUS = OPUS_MEDIUM


def _default_choice(is_pro: bool) -> ModelChoice:
    """Unlisted steps follow the tier at the deployment's configured model."""
    settings = get_settings()
    if is_pro:
        return ModelChoice(
            "anthropic",
            (getattr(settings, "ANTHROPIC_MODEL", "") or "claude-opus-5-5").strip(),
            (getattr(settings, "ANTHROPIC_EFFORT", "") or "medium").strip(),
        )
    return ModelChoice("groq", (getattr(settings, "GROQ_MODEL", "") or "openai/gpt-oss-20b").strip())


def _pinned_provider() -> str | None:
    override = (getattr(get_settings(), "AI_PROVIDER", "") or "").strip().lower()
    return override if override in TEXT_PROVIDERS else None


def model_for_step(is_pro: bool, step: str | None = None) -> ModelChoice:
    """What a step runs on for a tier, honouring the deployment's pin.

    ``AI_PROVIDER`` set to a real provider pins every step to it -- for local
    work and A/B runs, so a pinned run really is single-provider. Left at
    ``auto`` it means "decide per user and per step", which production wants.
    """
    free, pro = STEP_MODELS.get(step or "", (_default_choice(False), _default_choice(True)))
    choice = pro if is_pro else free
    pinned = _pinned_provider()
    if pinned is None or pinned == choice.provider:
        return choice
    # Pinned to the other provider: keep the step's intent (cheap or strong).
    other = free if pinned == free.provider else pro
    if other.provider == pinned:
        return other
    fallback = _default_choice(pinned == "anthropic")
    return ModelChoice(fallback.provider, fallback.model, "low" if pinned == "anthropic" else None)


def provider_for_tier(is_pro: bool, step: str | None = None) -> str:
    return model_for_step(is_pro, step).provider


def get_ai(provider: str) -> BaseAI:
    """Factory: returns an initialized AI client for the given provider."""
    try:
        return _REGISTRY[provider]()
    except KeyError:
        raise ValueError(f"Unknown provider '{provider}'. Available: {list(_REGISTRY)}")


def _has_key(provider: str) -> bool:
    key_setting = "ANTHROPIC_API_KEY" if provider == "anthropic" else "GROQ_API_KEY"
    return bool((getattr(get_settings(), key_setting, "") or "").strip())


def _build(choice: ModelChoice) -> BaseAI:
    if choice.provider == "anthropic":
        return Anthropic(model=choice.model, effort=choice.effort)
    return Groq(model=choice.model)


def get_text_client(
    provider: str | None = None,
    is_pro: bool | None = None,
    step: str | None = None,
    choice: ModelChoice | None = None,
) -> BaseAI:
    """The client a text step of the pipeline runs on.

    Pass ``is_pro`` and ``step`` to use the plan's model for that step; pass
    ``provider`` to force one at its configured default model, or ``choice``
    for an exact model (e.g. a flag-selected upgrade for one step). An unknown or
    unconfigured provider falls back to the other rather than failing the run,
    and says so in the log -- a paid user briefly getting the free model is far
    better than their job dying.
    """
    if choice is None and provider is not None:
        name = provider.strip().lower()
        if name not in TEXT_PROVIDERS:
            log.error(
                "Provider %r is not a text provider (choose from %s); falling back to %s",
                name, list(TEXT_PROVIDERS), DEFAULT_TEXT_PROVIDER,
            )
            name = DEFAULT_TEXT_PROVIDER
        choice = _default_choice(name == "anthropic")
    elif choice is None:
        choice = model_for_step(bool(is_pro), step)

    # A provider selected without a key would fail on every call with an opaque
    # auth error part-way through a run; catching it here names the cause.
    if not _has_key(choice.provider):
        other = "groq" if choice.provider == "anthropic" else "anthropic"
        if _has_key(other):
            log.error("%s API key is not set; step %s falls back to %s", choice.provider, step, other)
            choice = model_for_step(other == "anthropic", step)
            if choice.provider != other:
                choice = _default_choice(other == "anthropic")
        else:
            log.error("No API key is set for %s; calls will fail", choice.provider)

    return _build(choice)


__all__ = [
    "BaseAI",
    "provider_for_tier",
    "model_for_step",
    "ModelChoice",
    "STEP_MODELS",
    "PRO_TEXT_PROVIDER",
    "FREE_TEXT_PROVIDER",
    "OpenAI",
    "Anthropic",
    "XAI",
    "Groq",
    "get_ai",
    "get_text_client",
    "TEXT_PROVIDERS",
    "REEL_DIRECTOR_OPUS",
]
