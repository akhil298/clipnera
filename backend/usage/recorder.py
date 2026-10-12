"""Turns a provider's usage report into a costed ledger row.

Calls made outside any scope (tests, ad-hoc scripts) are only logged: there is
no project or user to charge them to, and writing them would mix test traffic
into the spend figures. Recording never raises into the AI call it describes.
"""

from __future__ import annotations

from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from usage.context import current_scope
from usage.model import LlmUsage
from usage.pricing import audio_cost, token_cost, video_cost

log = get_logger(__name__)


async def record_llm_call(
    provider: str,
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    audio_seconds: float | None = None,
    video_seconds: float | None = None,
    resolution: str | None = None,
    effort: str | None = None,
    latency_ms: int = 0,
    response: str | None = None,
    role: str | None = None,
) -> float:
    """Cost the call, charge the run's budget, log it and persist a row. Returns the cost in USD.

    ``response`` is what the model answered; it is logged in full on the same
    line, so the log shows every AI decision the run was built on. ``role`` is
    the AI-editor role the call was made for (clients.ai.roles), if any.
    """
    if video_seconds is not None:
        cost = video_cost(provider, model, resolution or "720p", video_seconds)
    elif audio_seconds is not None:
        cost = audio_cost(provider, model, audio_seconds)
    else:
        cost = token_cost(provider, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)

    scope = current_scope()
    log.info("AI %s/%s%s %s %.1fs $%.5f%s", provider, model, f" [{role}]" if role else "", _usage_summary(
        input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, audio_seconds, video_seconds,
    ), latency_ms / 1000, cost, f" -> {' '.join(response.split())}" if response else "")
    if scope is not None and scope.budget is not None:
        scope.budget.charge(cost)
    # Calls with neither a project nor a user (tests, scripts) are only logged. AI-editor calls carry
    # the user but no pipeline project (llm_usage.project_id points at video projects), and are kept.
    if scope is None or (scope.project_id is None and scope.user_id is None):
        return cost

    try:
        async with AsyncSessionLocal() as session:
            session.add(LlmUsage(
                project_id=scope.project_id,
                user_id=scope.user_id,
                step=scope.step,
                role=role,
                provider=provider,
                model=model,
                effort=effort,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
                audio_seconds=audio_seconds,
                cost_usd=cost,
                latency_ms=latency_ms,
            ))
            await session.commit()
    except Exception as exc:
        log.warning("Could not record AI usage for project %s: %s", scope.project_id, exc)
    return cost


def _usage_summary(
    input_tokens: int, output_tokens: int, cache_read: int, cache_write: int,
    audio_seconds: float | None, video_seconds: float | None,
) -> str:
    """Only the measures this call has, e.g. ``in=1200 out=340`` or ``audio=312.0s``."""
    if video_seconds is not None:
        return f"video={video_seconds:.1f}s"
    if audio_seconds is not None:
        return f"audio={audio_seconds:.1f}s"
    parts = [f"in={input_tokens}", f"out={output_tokens}"]
    if cache_read:
        parts.append(f"cache_read={cache_read}")
    if cache_write:
        parts.append(f"cache_write={cache_write}")
    return " ".join(parts)
