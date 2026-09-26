"""Turns a provider's usage report into a costed ledger row.

Calls made outside a pipeline scope (tests, ad-hoc scripts) are only logged:
there is no project to charge them to, and writing them would mix test traffic
into the spend figures. Recording never raises into the AI call it describes.
"""

from __future__ import annotations

from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from usage.context import current_scope
from usage.model import LlmUsage
from usage.pricing import audio_cost, token_cost

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
    effort: str | None = None,
    latency_ms: int = 0,
) -> float:
    """Cost the call, charge the run's budget and persist a row. Returns the cost in USD."""
    if audio_seconds is not None:
        cost = audio_cost(provider, model, audio_seconds)
    else:
        cost = token_cost(provider, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)

    scope = current_scope()
    log.info(
        "AI usage: step=%s %s/%s in=%d out=%d cache_read=%d cache_write=%d audio_s=%s cost=$%.5f",
        scope.step if scope else "unscoped", provider, model, input_tokens, output_tokens,
        cache_read_tokens, cache_write_tokens,
        f"{audio_seconds:.1f}" if audio_seconds is not None else "-", cost,
    )
    if scope is None or scope.project_id is None:
        return cost
    if scope.budget is not None:
        scope.budget.charge(cost)

    try:
        async with AsyncSessionLocal() as session:
            session.add(LlmUsage(
                project_id=scope.project_id,
                user_id=scope.user_id,
                step=scope.step,
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
