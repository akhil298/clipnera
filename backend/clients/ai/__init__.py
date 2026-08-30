from .base import BaseAI
from .openai import OpenAI
from .anthropic import Anthropic
from .xai import XAI
from .gemini import Gemini

Registry = dict[str, type[BaseAI]]

_REGISTRY: Registry = {
    "openai": OpenAI,
    "anthropic": Anthropic,
    "xai": XAI,
    "gemini": Gemini,
}


def get_ai(provider: str) -> BaseAI:
    """Factory: returns an initialized AI client for the given provider."""
    try:
        return _REGISTRY[provider]()
    except KeyError:
        raise ValueError(f"Unknown provider '{provider}'. Available: {list(_REGISTRY)}")


__all__ = [
    "BaseAI",
    "OpenAI",
    "Anthropic",
    "XAI",
    "Gemini",
    "get_ai",
]
