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

# Which provider each tier runs on. Pro buys the 1M-context, schema-enforced
# path; free runs on Groq's free tier. Both produce clips -- the difference is
# how much of the video the model sees at once and how strictly its output is
# constrained.
PRO_TEXT_PROVIDER = "anthropic"
FREE_TEXT_PROVIDER = "groq"

# Which provider each pipeline step runs on. The tiers differ enormously in what
# they cost, and the steps differ enormously in how much judgement they need --
# and the most expensive step needs the least. Pinning the mechanical steps to
# the free provider keeps spend on the calls where being right matters.
#
#   "groq" -- always the free provider, whatever the user pays
#   "tier" -- follows is_pro
#
# A step missing from this map follows the tier, so a new step is never silently
# downgraded; it just costs what the tier costs until it is classified here.
STEP_POLICY: dict[str, str] = {
    # Picks one of 13 enum values from the research summary; 163 tokens a video.
    "classification": "groq",
    # Mechanical word-to-emoji-id lookup, re-validated against the catalog
    # afterwards regardless, and by far the highest call volume in the pipeline.
    "emoji_cues": "groq",
    # A 1M window reads the whole transcript instead of its first quarter.
    "topic_research": "tier",
    # The product: which moments become clips.
    "highlight_detection": "tier",
    # Burned into the exported video as the headline, so it drives click-through.
    "titles": "tier",
}


def get_ai(provider: str) -> BaseAI:
    """Factory: returns an initialized AI client for the given provider."""
    try:
        return _REGISTRY[provider]()
    except KeyError:
        raise ValueError(f"Unknown provider '{provider}'. Available: {list(_REGISTRY)}")


def provider_for_tier(is_pro: bool, step: str | None = None) -> str:
    """Provider name for a tier and step, honouring the deployment's override.

    ``AI_PROVIDER`` pins every run to one provider when set to a real provider
    name -- useful for local work and for A/B runs, and it outranks the step
    policy so a pinned run really is single-provider. Left at its default it
    means "decide per user and per step", which is what production wants.
    """
    settings = get_settings()
    override = (getattr(settings, "AI_PROVIDER", "") or "").strip().lower()
    if override in TEXT_PROVIDERS:
        return override
    if step is not None and STEP_POLICY.get(step, "tier") == "groq":
        return FREE_TEXT_PROVIDER
    return PRO_TEXT_PROVIDER if is_pro else FREE_TEXT_PROVIDER


def get_text_client(
    provider: str | None = None,
    is_pro: bool | None = None,
    step: str | None = None,
) -> BaseAI:
    """The client a text step of the pipeline runs on.

    Pass ``is_pro`` to pick per user and ``step`` to apply the step policy on
    top; pass ``provider`` to force one. An unknown or unconfigured provider
    falls back to the free-tier default rather than failing the run, and says so
    in the log -- a paid user briefly getting the free model is far better than
    their job dying.
    """
    settings = get_settings()
    if provider is None and is_pro is not None:
        provider = provider_for_tier(is_pro, step)
    name = (provider or getattr(settings, "AI_PROVIDER", DEFAULT_TEXT_PROVIDER) or DEFAULT_TEXT_PROVIDER)
    name = name.strip().lower()

    client_cls = TEXT_PROVIDERS.get(name)
    if client_cls is None:
        log.error(
            "AI_PROVIDER=%r is not a text provider (choose from %s); falling back to %s",
            name, list(TEXT_PROVIDERS), DEFAULT_TEXT_PROVIDER,
        )
        client_cls = TEXT_PROVIDERS[DEFAULT_TEXT_PROVIDER]
        name = DEFAULT_TEXT_PROVIDER

    # A provider selected without a key would fail on every call with an opaque
    # auth error part-way through a run; catching it here names the cause.
    key_setting = "ANTHROPIC_API_KEY" if name == "anthropic" else "GROQ_API_KEY"
    if not (getattr(settings, key_setting, "") or "").strip():
        other = "groq" if name == "anthropic" else "anthropic"
        other_key = "GROQ_API_KEY" if other == "groq" else "ANTHROPIC_API_KEY"
        if (getattr(settings, other_key, "") or "").strip():
            log.error(
                "AI_PROVIDER=%s but %s is not set; falling back to %s, which is configured",
                name, key_setting, other,
            )
            return TEXT_PROVIDERS[other]()
        log.error("AI_PROVIDER=%s but %s is not set; calls will fail", name, key_setting)

    return client_cls()


__all__ = [
    "BaseAI",
    "provider_for_tier",
    "STEP_POLICY",
    "PRO_TEXT_PROVIDER",
    "FREE_TEXT_PROVIDER",
    "OpenAI",
    "Anthropic",
    "XAI",
    "Groq",
    "get_ai",
    "get_text_client",
    "TEXT_PROVIDERS",
]
