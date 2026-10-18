"""Which model each AI-editor role runs on, and switching between OpenAI and Anthropic.

A role is a job the editor's brain does (route a prompt, plan an edit, review a
render...). ``LLM_PROFILE`` picks a model per role for the whole deployment;
``LLM_ROLE_MODELS`` pins single roles over it, and a plan or a request may pin
one too. Pins are ``"provider:model"`` strings, or a bare provider for its
configured model.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal, TypeVar, get_args

import anthropic
import httpx

from core.config import get_settings
from core.logging_config import get_logger

from . import TEXT_PROVIDERS, ModelChoice, _build, _configured, _has_key
from .base import BaseAI

log = get_logger(__name__)

T = TypeVar("T")

Role = Literal[
    "router", "director", "director_delta", "specialist", "critic",
    "judge", "answer", "moderation", "captioner", "summarizer", "studio",
]

ROLES: dict[Role, str] = {
    "router": "Classifies a prompt: micro edit, plan, question or control.",
    "director": "Plans a multi-step edit from the user's brief and the media.",
    "director_delta": "Revises an existing plan after the user changes the brief.",
    "specialist": "Carries out one plan step (cut, audio, text, colour...) with editor tools.",
    "critic": "Reviews a rendered cut from contact sheets and asks for fixes.",
    "judge": "Scores candidate plans against the brief to pick the best.",
    "answer": "Answers questions about the project and its media, with no edit tools.",
    "moderation": "Flags prompts and uploaded text that must not be acted on.",
    "captioner": "Describes shots and frames in a line each.",
    "summarizer": "Condenses transcripts and long context for the other roles.",
    "studio": "Works the open project from the chat with every tool: reads, edits, looks at frames, drives the studio.",
}

HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"

# Thinking per role. None asks for the least the model allows: routing and
# moderation are classification, where thinking only adds latency.
ROLE_EFFORT: dict[Role, str | None] = {
    "router": None,
    "moderation": None,
    "answer": "low",
    "captioner": "low",
    "summarizer": "low",
    "specialist": "medium",
    "studio": "medium",
    "director_delta": "medium",
    "director": "high",
    "critic": "high",
    "judge": "high",
}

# Sampling temperature per role, for the models that still accept one.
ROLE_TEMPERATURE: dict[Role, float] = {"router": 0.0, "moderation": 0.0}

# The lowest effort each provider takes: Claude 5.x cannot turn thinking off.
_LEAST_EFFORT = {"anthropic": "low", "openai": "minimal"}

_OPENAI = ModelChoice("openai")

# Reasoning effort the user may pick in the studio. Routing and moderation keep theirs: they classify.
Effort = Literal["low", "medium", "high", "xhigh"]
EFFORTS: tuple[str, ...] = get_args(Effort)
_OWN_EFFORT: frozenset[Role] = frozenset({"router", "moderation"})

# The OpenAI deployment and effort picked for this turn or plan (``picked_model``).
_picked: ContextVar[tuple[str | None, str | None]] = ContextVar("picked_model", default=(None, None))

PROFILES: dict[str, dict[Role, ModelChoice]] = {
    "openai": {role: _OPENAI for role in ROLES},
    "anthropic": {
        "router": ModelChoice("anthropic", HAIKU),
        "answer": ModelChoice("anthropic", HAIKU),
        "moderation": ModelChoice("anthropic", HAIKU),
        "captioner": ModelChoice("anthropic", HAIKU),
        "director": ModelChoice("anthropic", OPUS),
        "critic": ModelChoice("anthropic", OPUS),
        "judge": ModelChoice("anthropic", OPUS),
        "director_delta": ModelChoice("anthropic", SONNET),
        "specialist": ModelChoice("anthropic", SONNET),
        "studio": ModelChoice("anthropic", SONNET),
        "summarizer": ModelChoice("anthropic", SONNET),
    },
}
# Judgement on Opus, volume on OpenAI.
PROFILES["mixed"] = {
    role: PROFILES["anthropic"][role] if role in ("director", "critic", "judge") else _OPENAI
    for role in ROLES
}


def parse_pin(pin: str) -> ModelChoice:
    """``"provider:model"`` (or a bare provider) as a choice; an unknown provider raises."""
    provider, _, model = pin.strip().partition(":")
    provider = provider.strip().lower()
    if provider not in TEXT_PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r} in model pin {pin!r}. Choose from {list(TEXT_PROVIDERS)}.")
    return ModelChoice(provider, model.strip())


def _check_role(role: str) -> Role:
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}. Choose from {list(ROLES)}.")
    return role  # type: ignore[return-value]


def selectable_models() -> list[str]:
    """OpenAI deployments the studio offers, the configured one first."""
    settings = get_settings()
    return list(dict.fromkeys([settings.OPENAI_MODEL, *settings.OPENAI_MODELS]))


@contextmanager
def picked_model(model: str | None, effort: str | None) -> Iterator[None]:
    """Run every role on OpenAI deployment ``model`` at ``effort`` (either may be None) within the block."""
    token = _picked.set((model, effort))
    try:
        yield
    finally:
        _picked.reset(token)


def current_pick() -> tuple[str | None, str | None]:
    """The (model, effort) picked for the running turn or plan."""
    return _picked.get()


def _with_role_effort(role: Role, choice: ModelChoice) -> ModelChoice:
    picked = _picked.get()[1] if choice.provider == "openai" and role not in _OWN_EFFORT else None
    effort = picked or ROLE_EFFORT[role] or _LEAST_EFFORT.get(choice.provider)
    return _configured(ModelChoice(choice.provider, choice.model, effort))


def model_for_role(role: str, plan_override: str | None = None, request_override: str | None = None) -> ModelChoice:
    """The model ``role`` runs on: request pin, then the studio's pick, deployment pin, plan pin, the profile."""
    role = _check_role(role)
    settings = get_settings()
    picked = _picked.get()[0]
    pin = request_override or (picked and f"openai:{picked}") or (settings.LLM_ROLE_MODELS or {}).get(role) or plan_override
    choice = parse_pin(pin) if pin else PROFILES[settings.LLM_PROFILE][role]
    return _with_role_effort(role, choice)


def _role_on(role: Role, provider: str) -> ModelChoice:
    """``role`` on ``provider``: the model a profile gives it there, else the provider's configured one."""
    choice = next((p[role] for p in PROFILES.values() if p[role].provider == provider), ModelChoice(provider))
    return _with_role_effort(role, choice)


def _chain(role: Role, first: ModelChoice) -> list[ModelChoice]:
    """``first``, then the role on each other ``LLM_FALLBACK`` provider; keyless providers are skipped."""
    others = [p for p in dict.fromkeys(get_settings().LLM_FALLBACK) if p != first.provider and p in TEXT_PROVIDERS]
    chain = [first, *(_role_on(role, p) for p in others)]
    usable = [choice for choice in chain if _has_key(choice.provider)]
    if not usable:
        log.error("No API key is set for any provider of role %s; calls will fail", role)
    return usable or chain[:1]


def _client(role: Role, choice: ModelChoice) -> BaseAI:
    client = _build(choice)
    client.role = role
    client.temperature = ROLE_TEMPERATURE.get(role)
    settings = get_settings()
    if settings.LLM_MODE != "live":
        # Evals: record every reply, or replay them without calling the API (clients.ai.cassette).
        from .cassette import CassetteClient

        return CassetteClient(client, settings.LLM_MODE, settings.LLM_PROFILE)
    return client


def get_role_client(role: str, *, plan_override: str | None = None, request_override: str | None = None) -> BaseAI:
    """A client for ``role``, carrying its effort and temperature as call defaults.

    A provider without a key gives way to the next in ``LLM_FALLBACK``.
    """
    role = _check_role(role)
    choice = _chain(role, model_for_role(role, plan_override, request_override))[0]
    return _client(role, choice)


def is_transient(exc: BaseException) -> bool:
    """Whether another provider might succeed: a rate limit, a server error or a timeout -- never a 4xx."""
    response = getattr(exc, "response", None)
    status = getattr(exc, "status_code", None) or getattr(response, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    return isinstance(exc, (httpx.TransportError, anthropic.APIConnectionError, TimeoutError, asyncio.TimeoutError))


async def call_with_fallback(role: str, fn: Callable[[BaseAI], Awaitable[T]], *,
                             plan_override: str | None = None, request_override: str | None = None) -> T:
    """Run ``fn`` on the role's client, moving down ``LLM_FALLBACK`` when a provider is down or busy.

    For self-contained calls only: a tool loop's history is in one provider's
    format, so a loop keeps the client it started on.
    """
    role = _check_role(role)
    chain = _chain(role, model_for_role(role, plan_override, request_override))
    for attempt, choice in enumerate(chain, start=1):
        client = _client(role, choice)
        try:
            return await fn(client)
        except Exception as exc:
            if attempt == len(chain) or not is_transient(exc):
                raise
            log.warning(
                "Role %s failed on %s/%s (attempt %d of %d, %s: %s); trying %s",
                role, choice.provider, choice.model, attempt, len(chain), type(exc).__name__, exc,
                chain[attempt].provider,
            )
        finally:
            await client.close()
    raise RuntimeError("Unreachable")  # pragma: no cover


__all__ = [
    "Role", "ROLES", "PROFILES", "ROLE_EFFORT", "ROLE_TEMPERATURE", "Effort", "EFFORTS",
    "selectable_models", "picked_model", "current_pick",
    "model_for_role", "parse_pin", "get_role_client", "call_with_fallback", "is_transient",
]
