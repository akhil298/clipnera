"""Plans as the user sees them: saved from the director, shown as a card, approved, rejected, edited.

Approving holds the plan's credit ceiling and queues its execution (brain.execute). The
runner-up is kept for a day so "try the other version" needs no new planning.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brain import credits
from brain.director import DirectorResult
from brain.model import EditPlan, PlanStatus, PlanStepRow, StepStatus
from brain.plan_ir import PlanIR
from brain.schema import GhostClip, PlanCard, PlanCardStep, PlanPatch
from brain.score import STEP_CREDITS, ScoredPlan
from core.exceptions import CustomException
from editor.timeline import ClipItem
from jobs.queue import Job, get_queue
from subscription.service import InsufficientCreditsError, SubscriptionService

EXECUTE_JOB = "brain.execute"


def log_step_id(plan_id: str, step_id: str) -> str:
    """The op log's step id for a plan step (what POST .../steps/{id}/undo takes)."""
    return f"plan-{plan_id[:8]}-{step_id}"[:60]
RUNNER_UP_HOURS = 24
FINAL = {PlanStatus.DONE, PlanStatus.FAILED, PlanStatus.REJECTED, PlanStatus.STOPPED}


def _ghost(scored: ScoredPlan) -> list[GhostClip]:
    timeline = scored.compiled.timeline
    main = next((t for t in timeline.tracks if t.kind == "video" and t.extra.get("role") == "main"), None)
    main = main or next((t for t in timeline.tracks if t.kind == "video"), None)
    return [GhostClip(at=i.at, end=i.end, label=f"Shot {n + 1}")
            for n, i in enumerate(main.items if main else []) if isinstance(i, ClipItem)]


def _result_line(scored: ScoredPlan) -> str:
    timeline = scored.compiled.timeline
    shots = len(_ghost(scored))
    parts = [f"{timeline.duration / timeline.fps:.1f} s", f"{shots} shot{'s' if shots != 1 else ''}"]
    if any(s.kind == "beat_sync" for s in scored.plan.steps):
        parts.append("on the beat")
    if any(s.kind == "flash" for s in scored.plan.steps):
        parts.append("flashes on drops")
    return " · ".join(parts)


async def save(session: AsyncSession, user_id: str, project_id: str, prompt: str, base_version: int,
               result: DirectorResult) -> EditPlan:
    best = result.best
    assert best is not None
    scores = {**best.summary(), "result_line": _result_line(best),
              "ghost": [g.model_dump() for g in _ghost(best)], "fps": best.compiled.timeline.fps}
    plan = EditPlan(
        project_id=project_id, user_id=user_id, prompt=prompt, status=PlanStatus.PROPOSED, base_version=base_version,
        plan=best.plan.model_dump_json(), frame=(result.frame.model_dump_json() if result.frame else "{}"),
        scores=json.dumps(scores), credits=best.credits, reason=result.reason[:1000],
        runner_up=result.runner_up.plan.model_dump_json() if result.runner_up else None,
        runner_up_expires_at=datetime.utcnow() + timedelta(hours=RUNNER_UP_HOURS) if result.runner_up else None,
    )
    session.add(plan)
    await session.flush()
    errors = {s.step_id: s.error for s in best.compiled.steps}
    for position, step in enumerate(best.plan.steps):
        session.add(PlanStepRow(plan_id=plan.id, step_id=step.id, position=position, kind=step.kind, intent=step.intent,
                                why=step.why, enabled=True, status=StepStatus.PENDING, credits=STEP_CREDITS,
                                note=errors.get(step.id) or ""))
    await session.commit()
    return plan


async def card(session: AsyncSession, plan: EditPlan) -> PlanCard:
    steps = await _steps(session, plan.id)
    ir = PlanIR.model_validate_json(plan.plan)
    frame = json.loads(plan.frame or "{}")
    scores = json.loads(plan.scores)
    by_id = {s.id: s for s in ir.steps}
    runner_up = None
    if plan.runner_up and plan.runner_up_expires_at and plan.runner_up_expires_at > datetime.utcnow():
        runner_up = PlanIR.model_validate_json(plan.runner_up).title
    return PlanCard(
        id=plan.id, status=plan.status, title=ir.title, summary=ir.summary,  # type: ignore[arg-type]
        result_line=scores.get("result_line", ""), credits=credits.to_clipnera(plan.credits),
        credits_charged=plan.credits_charged,
        steps=[PlanCardStep(id=s.step_id, kind=s.kind, intent=s.intent, why=s.why, enabled=s.enabled,
                            optional=by_id[s.step_id].optional if s.step_id in by_id else False,
                            status=s.status, credits=credits.to_clipnera(s.credits),  # type: ignore[arg-type]
                            depends_on=by_id[s.step_id].depends_on if s.step_id in by_id else [], note=s.note,
                            undo_step_id=log_step_id(plan.id, s.step_id) if s.status == StepStatus.DONE else None)
               for s in steps],
        assumptions=frame.get("assumptions", []), warnings=scores.get("warnings", []), premium=[],
        ghost=[GhostClip(**g) for g in scores.get("ghost", [])], fps=int(scores.get("fps", 30)),
        runner_up_title=runner_up, error=plan.error,
    )


async def _steps(session: AsyncSession, plan_id: str) -> list[PlanStepRow]:
    return list(await session.scalars(select(PlanStepRow).where(PlanStepRow.plan_id == plan_id)
                                      .order_by(PlanStepRow.position)))


async def get(session: AsyncSession, user_id: str, plan_id: str, *, lock: bool = False) -> EditPlan:
    query = select(EditPlan).where(EditPlan.id == plan_id, EditPlan.user_id == user_id)
    plan = await session.scalar(query.with_for_update() if lock else query)
    if plan is None:
        raise CustomException(message="Plan not found.", code="NOT_FOUND", status_code=404)
    return plan


async def approve(session: AsyncSession, user_id: str, plan_id: str) -> EditPlan:
    plan = await get(session, user_id, plan_id, lock=True)
    if plan.status != PlanStatus.PROPOSED:
        raise CustomException(message=f"This plan is {plan.status}; only a proposed plan can be approved.",
                              code="PLAN_NOT_PROPOSED", status_code=409)
    enabled = [s for s in await _steps(session, plan.id) if s.enabled]
    if not enabled:
        raise CustomException(message="Turn on at least one step to run.", code="NO_STEPS", status_code=422)
    ceiling = plan.credits - STEP_CREDITS * (len(await _steps(session, plan.id)) - len(enabled))
    try:
        plan.credits_held = await credits.hold(SubscriptionService.for_session(session), user_id, plan.id, ceiling)
    except InsufficientCreditsError:
        await session.rollback()
        raise CustomException(message="You don't have enough credits for this plan.", code="INSUFFICIENT_CREDITS",
                              status_code=402) from None
    plan.status = PlanStatus.APPROVED
    await session.commit()
    await get_queue().enqueue(Job(EXECUTE_JOB, {"plan_id": plan.id, "user_id": user_id}))
    return plan


async def control(session: AsyncSession, user_id: str, plan_id: str, action: str) -> EditPlan:
    """Pause, resume or stop a running plan (11.5). Stopping keeps what's applied ("take over")."""
    plan = await get(session, user_id, plan_id, lock=True)
    allowed = {"pause": {PlanStatus.RUNNING, PlanStatus.APPROVED}, "resume": {PlanStatus.PAUSED},
               "stop": {PlanStatus.RUNNING, PlanStatus.APPROVED, PlanStatus.PAUSED}}[action]
    if plan.status not in allowed:
        raise CustomException(message=f"This plan is {plan.status}; it can't {action}.", code="PLAN_STATE", status_code=409)
    plan.status = {"pause": PlanStatus.PAUSED, "resume": PlanStatus.APPROVED, "stop": PlanStatus.STOPPED}[action]
    await session.commit()
    if action == "resume":
        # The job re-reads the timeline and re-solves the remaining steps against it.
        await get_queue().enqueue(Job(EXECUTE_JOB, {"plan_id": plan.id, "user_id": user_id}))
    if action == "stop":
        await settle(session, plan)
    return plan


async def settle(session: AsyncSession, plan: EditPlan) -> None:
    """Charge the finished steps of a stopped plan and give back the rest of the hold."""
    from brain.score import FULL_PLAN_CREDITS, QUICK_PLAN_CREDITS, QUICK_PLAN_MAX_STEPS

    steps = await _steps(session, plan.id)
    done = [s for s in steps if s.status == StepStatus.DONE]
    base = QUICK_PLAN_CREDITS if len(steps) <= QUICK_PLAN_MAX_STEPS else FULL_PLAN_CREDITS
    committed = (base + STEP_CREDITS * len(done) if done else 0) + credits.CRITIC_ROUND * plan.review_rounds
    if plan.credits_held and not plan.credits_charged:
        plan.credits_charged = await credits.release(SubscriptionService.for_session(session), plan.user_id, plan.id,
                                                     plan.credits_held, committed)
        await session.commit()


async def reject(session: AsyncSession, user_id: str, plan_id: str) -> EditPlan:
    plan = await get(session, user_id, plan_id, lock=True)
    if plan.status != PlanStatus.PROPOSED:
        raise CustomException(message=f"This plan is {plan.status} and can't be rejected.", code="PLAN_NOT_PROPOSED",
                              status_code=409)
    plan.status = PlanStatus.REJECTED
    await session.commit()
    return plan


async def patch(session: AsyncSession, user_id: str, plan_id: str, change: PlanPatch) -> EditPlan:
    """Toggle and reorder steps of a proposed plan; a step can't run before what it depends on."""
    plan = await get(session, user_id, plan_id, lock=True)
    if plan.status != PlanStatus.PROPOSED:
        raise CustomException(message="Only a proposed plan can be edited.", code="PLAN_NOT_PROPOSED", status_code=409)
    steps = {s.step_id: s for s in await _steps(session, plan.id)}
    ir = {s.id: s for s in PlanIR.model_validate_json(plan.plan).steps}
    for step_id, on in change.enabled.items():
        if step_id not in steps:
            raise CustomException(message=f"There is no step {step_id}.", code="UNKNOWN_STEP", status_code=422)
        steps[step_id].enabled = on
    # A step whose dependency is off can't run either.
    for step_id, row in steps.items():
        if row.enabled and any(not steps[d].enabled for d in ir[step_id].depends_on if d in steps):
            row.enabled = False
    if change.order is not None:
        if sorted(change.order) != sorted(steps):
            raise CustomException(message="Name every step exactly once to reorder.", code="BAD_ORDER", status_code=422)
        seen: set[str] = set()
        for position, step_id in enumerate(change.order):
            missing = [d for d in ir[step_id].depends_on if d not in seen]
            if missing:
                raise CustomException(message=f"{step_id} has to come after {', '.join(missing)}.", code="BAD_ORDER",
                                      status_code=422)
            steps[step_id].position = position
            seen.add(step_id)
    await session.commit()
    return plan


async def alternative(session: AsyncSession, user_id: str, plan_id: str) -> EditPlan:
    """The runner-up as a new proposed plan, while it hasn't expired (9.4.4)."""
    plan = await get(session, user_id, plan_id)
    if not plan.runner_up or not plan.runner_up_expires_at or plan.runner_up_expires_at <= datetime.utcnow():
        raise CustomException(message="There's no other version to try any more.", code="NO_ALTERNATIVE", status_code=409)
    from brain.compile import compile_plan  # The other version is re-checked against the timeline as it is now.
    from brain.context import build_context
    from editor.service import EditorService
    from brain.intent import IntentFrame
    from brain.score import plan_score

    service = EditorService(session)
    ctx = await build_context(service, user_id, plan.project_id, selection=[], playhead=0, session=session)
    ir = PlanIR.model_validate_json(plan.runner_up)
    frame = IntentFrame.model_validate_json(plan.frame or "{}")
    compiled = compile_plan(ir, ctx.timeline, ctx.muds, human_owned=ctx.human_owned, style=ctx.style)
    scored = plan_score(0, ir, compiled, frame, ctx.muds, credits_left=ctx.credits_left, style=ctx.style)
    plan.runner_up = None
    result = DirectorResult("plan", best=scored, frame=frame, reason="The other version.")
    return await save(session, user_id, plan.project_id, plan.prompt, ctx.version, result)
