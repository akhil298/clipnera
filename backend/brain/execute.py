"""Run an approved plan (TODO Phase 11): step by step, each re-solved against the Timeline as it is now.

The job (``brain.execute``) walks the steps in dependency order. A step is compiled again
against the current head (a person may have edited since the plan was made) and applied as
one transaction under its own op-log step id, so the card's "Undo step" undoes exactly it. A
step the compiler can't express goes to its specialist (an LLM with editor tools behind the
ToolBroker). A failed step skips its dependents. Pause and stop are honoured between steps
and between a specialist's calls. Afterwards the verifier checks and repairs (Phase 12), the
critic reviews (Phase 13), and the unused credit hold is released (Phase 14).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from sqlalchemy import select

from brain.compile import compile_plan
from brain.context import build_context
from brain.model import EditPlan, PlanStatus, PlanStepRow, StepStatus
from brain.plan_ir import PlanIR, PlanStep
from brain.plans import EXECUTE_JOB, log_step_id, settle
from brain.specialists import SPECIALIST_FOR, run_specialist
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from editor.history import Actor
from editor.service import EditorService
from jobs.queue import Job, handler
from clients.ai.roles import picked_model
from usage.context import llm_scope

log = get_logger(__name__)

AUTHOR = "agent:director"
# Steps that rebuild or reshape the main cut never run at the same time as each other.
EXCLUSIVE = {"structure", "tighten", "beat_sync", "reframe"}


def waves(steps: Sequence[PlanStep]) -> list[list[PlanStep]]:
    """Steps grouped so each group only depends on earlier groups; reshaping steps get a group each."""
    placed: dict[str, int] = {}
    groups: list[list[PlanStep]] = []
    for step in steps:
        level = max((placed[d] + 1 for d in step.depends_on if d in placed), default=0)
        while level < len(groups) and step.kind in EXCLUSIVE and any(s.kind in EXCLUSIVE for s in groups[level]):
            level += 1
        if level == len(groups):
            groups.append([])
        groups[level].append(step)
        placed[step.id] = level
    return groups


@handler(EXECUTE_JOB)
async def execute_plan(job: Job) -> None:
    plan_id, user_id = job.payload["plan_id"], job.payload["user_id"]
    try:
        with llm_scope(user_id=user_id, step="editor_plan"), picked_model(*await _pick(plan_id)):
            await _execute(plan_id, user_id)
    except Exception as exc:
        log.exception("Plan execution failed: plan=%s", plan_id)
        await _finish(plan_id, user_id, PlanStatus.FAILED, error=f"The plan stopped: {exc}"[:500])


async def _pick(plan_id: str) -> tuple[str | None, str | None]:
    """The model and effort picked in the chat when the plan was made."""
    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, plan_id)
        return (plan.ai_model, plan.ai_effort) if plan else (None, None)


async def _execute(plan_id: str, user_id: str) -> None:
    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, plan_id)
        if plan is None or plan.status not in (PlanStatus.APPROVED, PlanStatus.PAUSED):
            return
        plan.status = PlanStatus.RUNNING
        await session.commit()
        ir = PlanIR.model_validate_json(plan.plan)
        rows = {r.step_id: r for r in await session.scalars(select(PlanStepRow).where(PlanStepRow.plan_id == plan_id))}

    order = sorted((s for s in ir.steps if rows[s.id].enabled), key=lambda s: rows[s.id].position)
    failed: set[str] = set()
    for wave in waves(order):
        if await _halted(plan_id):
            return
        runnable = []
        for step in wave:
            if rows[step.id].status == StepStatus.DONE:
                continue  # Resumed after a pause: done steps stay done.
            if failed & set(step.depends_on):
                await _set_step(plan_id, step.id, status=StepStatus.SKIPPED, note="Skipped: a step it needs failed.")
                failed.add(step.id)
                continue
            runnable.append(step)
        # One after another: every step edits the same project, so ops serialise anyway (BLUEPRINT §3.9.2);
        # a wave only says which steps may go in any order.
        for step in runnable:
            if await _halted(plan_id):
                return
            if not await _run_step(plan_id, user_id, ir, step):
                failed.add(step.id)

    if await _halted(plan_id):
        return
    from brain.verify import verify_and_repair  # Phase 12, after every step has run.

    await verify_and_repair(plan_id, user_id)
    await _finish(plan_id, user_id, PlanStatus.DONE if not failed else PlanStatus.FAILED,
                  error=None if not failed else f"{len(failed)} step(s) didn't finish; the rest are applied.")


async def _run_step(plan_id: str, user_id: str, ir: PlanIR, step: PlanStep) -> bool:
    await _set_step(plan_id, step.id, status=StepStatus.RUNNING, note="")
    async with AsyncSessionLocal() as session:
        service = EditorService(session)
        plan = await session.get(EditPlan, plan_id)
        assert plan is not None
        # Read now: a refused apply rolls the session back and the row can't be read after it.
        project_id = plan.project_id
        ctx = await build_context(service, user_id, project_id, selection=[], playhead=0, session=session)
        compiled = compile_plan(ir, ctx.timeline, ctx.muds, human_owned=ctx.human_owned, only=[step.id], style=ctx.style)
        out = compiled.steps[0]
        actor = Actor(author=AUTHOR, step_id=log_step_id(plan_id, step.id), turn_id=plan_id,
                      human_owned_ok=frozenset(ir.human_owned_ok), destructive_ok=True,
                      allowed_text=frozenset(t.content for t in ir.text), may_resize=step.kind == "reframe",
                      compiled=True)
        if out.error is None and out.ops:
            try:
                result = await service.apply(user_id, project_id, ctx.version, out.ops, actor)
            except CustomException as exc:
                out.error = f"{exc.code}: {exc.message}"
            else:
                note = "; ".join(out.warnings) or "Done."
                await _set_step(plan_id, step.id, status=StepStatus.DONE, note=note[:500], ops=len(out.ops),
                                version_after=result.version)
                return True
        elif out.error is None:
            await _set_step(plan_id, step.id, status=StepStatus.DONE, note="; ".join(out.warnings) or "Nothing to change.")
            return True

        if step.kind in SPECIALIST_FOR:
            # A model working the step out itself gets the small budget of a free-running agent.
            outcome = await run_specialist(service, user_id, project_id, plan_id, step, replace(actor, compiled=False),
                                           reason=out.error or "")
            await _set_step(plan_id, step.id, status=StepStatus.DONE if outcome.ok else StepStatus.FAILED,
                            note=outcome.note[:500], ops=outcome.ops, version_after=outcome.version)
            return outcome.ok
    await _set_step(plan_id, step.id, status=StepStatus.FAILED, note=(out.error or "Failed.")[:500])
    return False


async def _halted(plan_id: str) -> bool:
    """Paused or stopped by the user (11.5): the run ends here; resume starts a new job."""
    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, plan_id)
        return plan is None or plan.status in (PlanStatus.PAUSED, PlanStatus.STOPPED)


async def _set_step(plan_id: str, step_id: str, **fields: Any) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.scalar(select(PlanStepRow).where(PlanStepRow.plan_id == plan_id, PlanStepRow.step_id == step_id))
        if row is None:
            return
        for name, value in fields.items():
            setattr(row, name, value)
        await session.commit()


async def _finish(plan_id: str, user_id: str, status: str, error: str | None = None) -> None:
    """Close the plan: charge the finished steps and give back the rest of the hold (Phase 14)."""
    async with AsyncSessionLocal() as session:
        plan = await session.get(EditPlan, plan_id, with_for_update=True)
        if plan is None:
            return
        await settle(session, plan)
        plan.status = status
        plan.error = error
        await session.commit()
        log.info("Plan %s finished: %s, %d credits charged", plan_id, status, plan.credits_charged)
