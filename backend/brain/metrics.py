"""AI-editor rollout metrics (TODO 18.1.3): turns, cost per turn and how often AI edits get undone."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from brain.model import EditPlan
from editor.model import EditorOp
from usage.model import LlmUsage

EDITOR_STEPS = ("editor_turn", "editor_plan", "media_understanding")


async def rollout_metrics(session: AsyncSession, days: int) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    plans = await session.scalar(select(func.count()).select_from(EditPlan).where(EditPlan.created_at >= since)) or 0
    approved = await session.scalar(select(func.count()).select_from(EditPlan).where(
        EditPlan.created_at >= since, EditPlan.status.in_(["approved", "running", "paused", "done", "failed", "stopped"]))) or 0
    rows = list((await session.execute(select(EditorOp).where(EditorOp.created_at >= since))).scalars().all())
    # An AI step: one micro edit, or one step of a plan (its batches share a step id).
    ai_steps = {(r.project_id, r.step_id or f"v{r.version}") for r in rows if r.by_agent and r.kind == "edit"}
    by_version = {(r.project_id, r.version): r for r in rows}
    undone = set()
    for r in rows:
        if r.kind != "undo":
            continue
        for version in json.loads(r.targets or "[]"):
            target = by_version.get((r.project_id, version))
            if target is not None and target.by_agent:
                undone.add((target.project_id, target.step_id or f"v{target.version}"))
    turns = len({r.step_id for r in rows if r.author == "agent:micro" and r.step_id}) + plans
    usage = (await session.execute(select(LlmUsage.step, func.count(), func.sum(LlmUsage.cost_usd)).where(
        LlmUsage.created_at >= since, LlmUsage.step.in_(EDITOR_STEPS)).group_by(LlmUsage.step))).all()
    spend = {step: {"calls": calls, "usd": round(float(usd or 0), 4)} for step, calls, usd in usage}
    turn_usd = sum(v["usd"] for k, v in spend.items() if k in ("editor_turn", "editor_plan"))
    return {
        "days": days, "turns": turns, "plans": plans, "plans_approved": approved,
        "ai_steps": len(ai_steps), "ai_steps_undone": len(undone & ai_steps),
        "undo_rate": round(len(undone & ai_steps) / len(ai_steps), 3) if ai_steps else 0.0,
        "cost_per_turn_usd": round(turn_usd / turns, 4) if turns else 0.0, "spend": spend,
    }
