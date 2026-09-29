"""List prices, in US dollars, for every model the pipeline calls.

Anthropic rates are the first-party API prices; cache reads bill at 0.1x the
input rate and five-minute cache writes at 1.25x. Groq rates are as listed on
groq.com/pricing when this table was written -- check them there when Groq
changes a price, since nothing else in the code knows about it.

A model missing from the table is costed at zero and logged, so an unpriced
model shows up as a warning in the log rather than as a failed pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.logging_config import get_logger

log = get_logger(__name__)

CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


@dataclass(frozen=True)
class TokenPrice:
    input_per_mtok: float
    output_per_mtok: float


TOKEN_PRICES: dict[tuple[str, str], TokenPrice] = {
    ("anthropic", "claude-opus-5-5"): TokenPrice(4.00, 20.00),
    ("anthropic", "claude-opus-5"): TokenPrice(5.00, 25.00),
    ("anthropic", "claude-opus-4-8"): TokenPrice(5.00, 25.00),
    ("anthropic", "claude-sonnet-5"): TokenPrice(2.00, 10.00),
    ("anthropic", "claude-haiku-4-5"): TokenPrice(1.00, 5.00),
    ("groq", "openai/gpt-oss-20b"): TokenPrice(0.075, 0.30),
    ("groq", "openai/gpt-oss-120b"): TokenPrice(0.15, 0.60),
    # Gemini paid-tier rates for text, image and video input (ai.google.dev/gemini-api/docs/pricing).
    ("gemini", "gemini-3.1-flash-lite"): TokenPrice(0.25, 1.50),
    ("gemini", "gemini-3.5-flash-lite"): TokenPrice(0.30, 2.50),
}

# Speech-to-text, per hour of audio.
AUDIO_PRICES_PER_HOUR: dict[tuple[str, str], float] = {
    ("groq", "whisper-large-v3-turbo"): 0.04,
    ("groq", "whisper-large-v3"): 0.111,
}

# Generated video, per second of output, by resolution (Gemini API list prices).
VIDEO_PRICES_PER_SECOND: dict[tuple[str, str, str], float] = {
    ("gemini", "veo-3.1-lite-generate-preview", "720p"): 0.05,
    ("gemini", "veo-3.1-lite-generate-preview", "1080p"): 0.08,
    ("gemini", "veo-3.1-fast-generate-preview", "720p"): 0.10,
    ("gemini", "veo-3.1-fast-generate-preview", "1080p"): 0.12,
    ("gemini", "veo-3.1-generate-preview", "720p"): 0.40,
    ("gemini", "veo-3.1-generate-preview", "1080p"): 0.40,
}

_warned: set[tuple[str, str]] = set()


def _warn_unpriced(provider: str, model: str) -> None:
    if (provider, model) not in _warned:
        _warned.add((provider, model))
        log.warning("No price for %s/%s; its calls are recorded at $0", provider, model)


def token_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Dollar cost of one call. ``input_tokens`` excludes cached tokens, as the APIs report it."""
    price = TOKEN_PRICES.get((provider, model))
    if price is None:
        _warn_unpriced(provider, model)
        return 0.0
    billed_input = (
        input_tokens
        + cache_read_tokens * CACHE_READ_MULTIPLIER
        + cache_write_tokens * CACHE_WRITE_MULTIPLIER
    )
    return (billed_input * price.input_per_mtok + output_tokens * price.output_per_mtok) / 1_000_000


def video_cost(provider: str, model: str, resolution: str, seconds: float) -> float:
    per_second = VIDEO_PRICES_PER_SECOND.get((provider, model, resolution))
    if per_second is None:
        _warn_unpriced(provider, f"{model}@{resolution}")
        return 0.0
    return per_second * seconds


def audio_cost(provider: str, model: str, audio_seconds: float) -> float:
    per_hour = AUDIO_PRICES_PER_HOUR.get((provider, model))
    if per_hour is None:
        _warn_unpriced(provider, model)
        return 0.0
    return per_hour * audio_seconds / 3600.0
