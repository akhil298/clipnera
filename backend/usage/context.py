"""Which project, user and step an AI call is being made for, plus the run's budget.

Held in a ContextVar so the AI clients can attribute and cap spend without every
caller threading ids through. asyncio tasks and ``asyncio.to_thread`` copy the
context, so anything a step spawns is attributed to that step too.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Iterator

# Share of the cap after which remaining calls drop to the cheapest settings.
TIGHT_BUDGET_SHARE = 0.8


class LlmBudgetExceeded(RuntimeError):
    """Raised before a call once the run has spent its cap; callers fall back to heuristics."""


@dataclass
class RunBudget:
    """Dollar ceiling for one pipeline run. A cap of 0 means unlimited."""

    cap_usd: float
    spent_usd: float = 0.0

    def charge(self, usd: float) -> None:
        self.spent_usd += max(0.0, usd)

    @property
    def tight(self) -> bool:
        return self.cap_usd > 0 and self.spent_usd >= self.cap_usd * TIGHT_BUDGET_SHARE

    @property
    def exhausted(self) -> bool:
        return self.cap_usd > 0 and self.spent_usd >= self.cap_usd


@dataclass(frozen=True)
class LlmScope:
    project_id: str | None = None
    user_id: str | None = None
    step: str = "unscoped"
    budget: RunBudget | None = None


_scope: ContextVar[LlmScope | None] = ContextVar("llm_scope", default=None)


def current_scope() -> LlmScope | None:
    return _scope.get()


@contextmanager
def llm_scope(**changes: object) -> Iterator[LlmScope]:
    """Set (or refine) the scope for the calls made inside the block."""
    base = _scope.get() or LlmScope()
    scope = replace(base, **changes)
    token = _scope.set(scope)
    try:
        yield scope
    finally:
        _scope.reset(token)


def check_budget() -> RunBudget | None:
    """Raise if the current run is out of budget; return its budget otherwise."""
    scope = _scope.get()
    budget = scope.budget if scope else None
    if budget is not None and budget.exhausted:
        raise LlmBudgetExceeded(
            f"AI budget of ${budget.cap_usd:.2f} for this video is spent (${budget.spent_usd:.4f})"
        )
    return budget
