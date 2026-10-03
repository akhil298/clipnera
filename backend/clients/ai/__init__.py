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
    "openai": OpenAI,
}

DEFAULT_TEXT_PROVIDER = "groq"

PRO_TEXT_PROVIDER = "openai"
FREE_TEXT_PROVIDER = "groq"

# (model setting, its fallback, API key setting) for each text provider.
_PROVIDER_SETTINGS: dict[str, tuple[str, str, str]] = {
    "groq": ("GROQ_MODEL", "openai/gpt-oss-20b", "GROQ_API_KEY"),
    "anthropic": ("ANTHROPIC_MODEL", "claude-opus-5-5", "ANTHROPIC_API_KEY"),
    "openai": ("OPENAI_MODEL", "gpt-4o-mini", "OPENAI_API_KEY"),
}


@dataclass(frozen=True)
class ModelChoice:
    """Provider, model and (Anthropic only) effort for one step of one tier.

    An empty ``model`` means the one the deployment configured for the provider.
    """

    provider: str
    model: str = ""
    effort: str | None = None


GROQ_SMALL = ModelChoice("groq", "openai/gpt-oss-20b")
GROQ_LARGE = ModelChoice("groq", "openai/gpt-oss-120b")
# Pro runs on the deployment's OpenAI model (OPENAI_MODEL at OPENAI_ENDPOINT).
OPENAI_PRO = ModelChoice("openai")
OPUS_MEDIUM = ModelChoice("anthropic", "claude-opus-5-5", "medium")

# (free, pro) per step. Pro pays for OpenAI wherever the step needs judgement or
# writes what the viewer reads; the free tier runs entirely on Groq, and so do
# the steps that need no judgement, whatever the user pays.
STEP_MODELS: dict[str, tuple[ModelChoice, ModelChoice]] = {
    "classification": (GROQ_SMALL, GROQ_SMALL),
    "topic_research": (GROQ_SMALL, OPENAI_PRO),
    "map": (GROQ_SMALL, OPENAI_PRO),
    "highlight_detection": (GROQ_LARGE, OPENAI_PRO),
    "director": (GROQ_LARGE, OPENAI_PRO),
    "titles": (GROQ_SMALL, OPENAI_PRO),
    # Spelling words in Roman script needs no judgement; the large open model is plenty.
    "transliteration": (GROQ_SMALL, GROQ_LARGE),
    # Where to cut away and what to search for: editorial, but low stakes per call.
    "broll_planning": (GROQ_LARGE, OPENAI_PRO),
    # Footage reels: one call decides the whole edit. The reel editor's Opus
    # flag swaps in REEL_DIRECTOR_OPUS (see edit_engine.director).
    "reel_director": (GROQ_LARGE, OPENAI_PRO),
    # Turning a chat message into a few timeline edits needs little judgement.
    "reel_chat": (GROQ_SMALL, OPENAI_PRO),
    # Captions for a contact sheet of shots, and the Instagram caption.
    "reel_copy": (GROQ_SMALL, OPENAI_PRO),
    # The one line about the channel in a creator's intro.
    "intro_copy": (GROQ_SMALL, OPENAI_PRO),
}

REEL_DIRECTOR_OPUS = OPUS_MEDIUM


def _configured(choice: ModelChoice) -> ModelChoice:
    """``choice`` with an empty model filled in from the deployment's settings."""
    if choice.model:
        return choice
    settings = get_settings()
    model_setting, fallback, _ = _PROVIDER_SETTINGS[choice.provider]
    effort = choice.effort
    if choice.provider == "anthropic" and effort is None:
        effort = (getattr(settings, "ANTHROPIC_EFFORT", "") or "medium").strip()
    return ModelChoice(choice.provider, (getattr(settings, model_setting, "") or fallback).strip(), effort)


def _step_choices(step: str | None) -> tuple[ModelChoice, ModelChoice]:
    """(free, pro) for a step. Unlisted steps follow the tier at the configured model."""
    return STEP_MODELS.get(step or "", (ModelChoice(FREE_TEXT_PROVIDER), ModelChoice(PRO_TEXT_PROVIDER)))


def _on_provider(provider: str, step: str | None) -> ModelChoice:
    """The step on ``provider``: its own model there if it has one, else the configured model."""
    for choice in _step_choices(step):
        if choice.provider == provider:
            return choice
    # No model was chosen for this step on this provider; on Claude keep the thinking cheap.
    return ModelChoice(provider, effort="low" if provider == "anthropic" else None)


def _pinned_provider() -> str | None:
    override = (getattr(get_settings(), "AI_PROVIDER", "") or "").strip().lower()
    return override if override in TEXT_PROVIDERS else None


def model_for_step(is_pro: bool, step: str | None = None) -> ModelChoice:
    """What a step runs on for a tier, honouring the deployment's pin.

    ``AI_PROVIDER`` set to a real provider pins every step to it -- for local
    work and A/B runs, so a pinned run really is single-provider. Left at
    ``auto`` it means "decide per user and per step", which production wants.
    """
    free, pro = _step_choices(step)
    choice = pro if is_pro else free
    pinned = _pinned_provider()
    if pinned is not None and pinned != choice.provider:
        choice = _on_provider(pinned, step)
    return _configured(choice)


def provider_for_tier(is_pro: bool, step: str | None = None) -> str:
    return model_for_step(is_pro, step).provider


def get_ai(provider: str) -> BaseAI:
    """Factory: returns an initialized AI client for the given provider."""
    try:
        return _REGISTRY[provider]()
    except KeyError:
        raise ValueError(f"Unknown provider '{provider}'. Available: {list(_REGISTRY)}")


def _has_key(provider: str) -> bool:
    return bool((getattr(get_settings(), _PROVIDER_SETTINGS[provider][2], "") or "").strip())


def _build(choice: ModelChoice) -> BaseAI:
    if choice.provider == "anthropic":
        return Anthropic(model=choice.model, effort=choice.effort)
    return TEXT_PROVIDERS[choice.provider](model=choice.model)


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
    unconfigured provider falls back to another rather than failing the run,
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
        choice = _configured(ModelChoice(name))
    elif choice is None:
        choice = model_for_step(bool(is_pro), step)

    # A provider selected without a key would fail on every call with an opaque
    # auth error part-way through a run; catching it here names the cause.
    if not _has_key(choice.provider):
        # The free provider first, so a missing key never bills a dearer model by surprise.
        candidates = dict.fromkeys((FREE_TEXT_PROVIDER, PRO_TEXT_PROVIDER, *TEXT_PROVIDERS))
        other = next((name for name in candidates if name != choice.provider and _has_key(name)), None)
        if other:
            log.error("%s API key is not set; step %s falls back to %s", choice.provider, step, other)
            choice = _configured(_on_provider(other, step))
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
