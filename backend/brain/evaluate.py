"""evaluate_plan_candidates: validate, compile, dry-run and score the director's candidates (TODO 6.6, 9.4.5).

The director calls it once with every candidate and gets back, per candidate, whether it can
run and how good it is. Validation is the plan's contract with the user: steps form a DAG,
every asset is a real one, every explicit ask is met by some step, budgets hold, and nothing
the user made is touched unless the request named it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from brain.compile import compile_plan
from brain.context import EditContext
from brain.intent import IntentFrame
from brain.plan_ir import PlanIR, ref_errors
from brain.score import ScoredPlan, judge, plan_score, select_best
from editor.history import STEP_OP_BUDGET, TURN_OP_BUDGET


@dataclass
class Evaluation:
    scored: list[ScoredPlan] = field(default_factory=list)
    # Candidate index -> why it can't be used at all (validation failed before scoring).
    invalid: dict[int, list[str]] = field(default_factory=dict)

    def best(self) -> tuple[ScoredPlan | None, ScoredPlan | None]:
        return select_best(self.scored)

    def report(self) -> list[dict]:
        rows = [s.summary() for s in self.scored]
        rows += [{"candidate": f"c{i + 1}", "invalid": errors} for i, errors in sorted(self.invalid.items())]
        return sorted(rows, key=lambda r: r["candidate"])


def validate(plan: PlanIR, frame: IntentFrame, ctx: EditContext, allowed_owned: set[str]) -> list[str]:
    """6.6: everything a plan must satisfy before it is compiled and shown."""
    errors = ref_errors(plan, ctx.muds)
    known = set(ctx.timeline.assets)
    unknown_assets = sorted({r.asset for r in plan.moment_refs()} - known)
    if unknown_assets:
        errors.append(f"Unknown assets {unknown_assets}; use ids from the media list.")
    uncovered = sorted({a.id for a in frame.asks} - {ask for step in plan.steps for ask in step.satisfies})
    if uncovered:
        errors.append(f"No step satisfies asks {uncovered}; list them in a step's satisfies.")
    extra_owned = sorted(set(plan.human_owned_ok) - allowed_owned)
    if extra_owned:
        errors.append(f"human_owned_ok may only name items the user selected or named: {extra_owned} weren't.")
    return errors


async def evaluate_candidates(prompt: str, frame: IntentFrame, plans: Sequence[PlanIR], ctx: EditContext, *,
                              allowed_owned: set[str], use_judge: bool) -> Evaluation:
    result = Evaluation()
    for index, plan in enumerate(plans):
        errors = validate(plan, frame, ctx, allowed_owned)
        if errors:
            result.invalid[index] = errors
            continue
        compiled = compile_plan(plan, ctx.timeline, ctx.muds, human_owned=ctx.human_owned, style=ctx.style)
        too_big = [s.step_id for s in compiled.steps if len(s.ops) > STEP_OP_BUDGET]
        touched_owned = sorted(compiled.touched_items() & (ctx.human_owned - set(plan.human_owned_ok)))
        problems = []
        if too_big:
            problems.append(f"Steps {too_big} need more than {STEP_OP_BUDGET} operations; split them.")
        if compiled.op_count > TURN_OP_BUDGET:
            problems.append(f"The plan needs {compiled.op_count} operations; the limit is {TURN_OP_BUDGET}.")
        if touched_owned:
            problems.append(f"The plan changes items the user made: {touched_owned}.")
        if problems:
            result.invalid[index] = problems
            continue
        result.scored.append(plan_score(index, plan, compiled, frame, ctx.muds, credits_left=ctx.credits_left,
                                        genre=frame.genre if frame.genre in ("beat_edit", "tutorial") else "default",
                                        style=ctx.style))
    if use_judge and len(result.scored) > 1:
        verdicts = await judge(prompt, frame, result.scored)
        result.scored = [
            plan_score(s.index, s.plan, s.compiled, frame, ctx.muds, credits_left=ctx.credits_left,
                       judge=verdicts.get(f"c{s.index + 1}"),
                       genre=frame.genre if frame.genre in ("beat_edit", "tutorial") else "default", style=ctx.style)
            for s in result.scored
        ]
    return result
