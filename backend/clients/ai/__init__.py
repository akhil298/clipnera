from .base import BaseAI
from .openai import OpenAI
from .anthropic import Anthropic
from .xai import XAI
from .groq import Groq

Registry = dict[str, type[BaseAI]]

_REGISTRY: Registry = {
    "openai": OpenAI,
    "anthropic": Anthropic,
    "xai": XAI,
    "groq": Groq,
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
    "Groq",
    "get_ai",
]
