"""/editor/plans: the plan card's API (TODO 10.1, 11.4, 11.5). Responses mirrored in frontend/lib/api.ts."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import brain.execute  # noqa: F401 -- registers the plan execution job handler
from auth.dependencies import CurrentUserDep
from brain import plans
from brain.model import EditPlan, PlanStepRow
from brain import style
from brain import server_render
from auth.dependencies import get_current_admin
from brain.metrics import rollout_metrics
from brain.schema import LibrarySound, PlanCard, PlanPatch, RenderStatus, RolloutMetrics, SoundSearchResponse, StylePreference
from core.database import AsyncSessionLocal, get_db
from core.responses import ApiResponse, ok
from editor.model import EditorOp, EditorProject
from feature_flags.dependencies import require_user_flag
from feature_flags.registry import AGENT_EDITOR

router = APIRouter(prefix="/editor/plans", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
style_router = APIRouter(prefix="/editor/style", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
renders_router = APIRouter(prefix="/editor/projects", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
admin_router = APIRouter(prefix="/admin/ai-editor", tags=["admin"], dependencies=[Depends(get_current_admin)])
sounds_router = APIRouter(prefix="/editor/sounds", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
SOUND_TAGS = {"pop": ["pop", "bubble", "ui"], "click": ["click", "ui", "button"], "soft_click": ["click", "soft", "ui"],
              "whoosh": ["whoosh", "transition", "swoosh"], "whoosh_short": ["whoosh", "fast", "transition"],
              "ding": ["ding", "bell", "notification"], "cash": ["cash", "money", "register"],
              "tick": ["tick", "clock", "ui"], "boom": ["boom", "impact", "hit"], "riser": ["riser", "build", "tension"]}
SessionDep = Annotated[AsyncSession, Depends(get_db)]
STREAM_POLL_SECONDS = 1.0
STREAM_MAX_SECONDS = 20 * 60


@router.get("/{plan_id}", response_model=ApiResponse[PlanCard])
async def get_plan(plan_id: str, user: CurrentUserDep, session: SessionDep):
    return ok(await plans.card(session, await plans.get(session, user["user_id"], plan_id)))


@router.post("/{plan_id}/approve", response_model=ApiResponse[PlanCard])
async def approve(plan_id: str, user: CurrentUserDep, session: SessionDep):
    """Hold the plan's credit ceiling and start running it; 402 INSUFFICIENT_CREDITS if it doesn't fit."""
    return ok(await plans.card(session, await plans.approve(session, user["user_id"], plan_id)))


@router.post("/{plan_id}/reject", response_model=ApiResponse[PlanCard])
async def reject(plan_id: str, user: CurrentUserDep, session: SessionDep):
    return ok(await plans.card(session, await plans.reject(session, user["user_id"], plan_id)))


@router.patch("/{plan_id}", response_model=ApiResponse[PlanCard])
async def edit(plan_id: str, data: PlanPatch, user: CurrentUserDep, session: SessionDep):
    """Turn steps on or off and reorder them before approving."""
    return ok(await plans.card(session, await plans.patch(session, user["user_id"], plan_id, data)))


@router.post("/{plan_id}/pause", response_model=ApiResponse[PlanCard])
async def pause(plan_id: str, user: CurrentUserDep, session: SessionDep):
    return ok(await plans.card(session, await plans.control(session, user["user_id"], plan_id, "pause")))


@router.post("/{plan_id}/resume", response_model=ApiResponse[PlanCard])
async def resume(plan_id: str, user: CurrentUserDep, session: SessionDep):
    return ok(await plans.card(session, await plans.control(session, user["user_id"], plan_id, "resume")))


@router.post("/{plan_id}/stop", response_model=ApiResponse[PlanCard])
async def stop(plan_id: str, user: CurrentUserDep, session: SessionDep):
    """Stop for good, keeping every step already applied (the "Take over" button)."""
    return ok(await plans.card(session, await plans.control(session, user["user_id"], plan_id, "stop")))


@router.post("/{plan_id}/alternative", response_model=ApiResponse[PlanCard])
async def alternative(plan_id: str, user: CurrentUserDep, session: SessionDep):
    """The runner-up as a new proposed plan ("Try the other version"), within a day."""
    return ok(await plans.card(session, await plans.alternative(session, user["user_id"], plan_id)))


@router.get("/{plan_id}/stream")
async def stream(plan_id: str, user: CurrentUserDep, session: SessionDep):
    """Server-sent events while the plan runs: plan.updated, agent.step, op.applied (then the stream ends)."""
    plan = await plans.get(session, user["user_id"], plan_id)
    return StreamingResponse(_events(plan.id, plan.project_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _event(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n"


async def _events(plan_id: str, project_id: str) -> AsyncIterator[str]:
    """Polls the database, so it works whether the plan runs in this process or in a worker."""
    started, last_card, steps_seen, version_seen = time.monotonic(), None, {}, None
    while time.monotonic() - started < STREAM_MAX_SECONDS:
        async with AsyncSessionLocal() as session:
            plan = await session.get(EditPlan, plan_id)
            if plan is None:
                return
            card = (await plans.card(session, plan)).model_dump(mode="json")
            rows = list(await session.scalars(select(PlanStepRow).where(PlanStepRow.plan_id == plan_id)))
            version = await session.scalar(select(EditorProject.version).where(EditorProject.id == project_id))
            cursor = None
            if version != version_seen and version is not None:
                op = await session.scalar(select(EditorOp).where(EditorOp.project_id == project_id,
                                                                 EditorOp.version == version))
                cursor = _cursor(op)
        for row in rows:
            state = (row.status, row.note)
            if steps_seen.get(row.step_id) != state:
                steps_seen[row.step_id] = state
                yield _event("agent.step", {"step_id": row.step_id, "status": row.status, "note": row.note})
        if version_seen is not None and version != version_seen:
            yield _event("op.applied", {"version": version, "cursor": cursor})
        version_seen = version
        if card != last_card:
            last_card = card
            yield _event("plan.updated", card)
        if plan.status in plans.FINAL:
            yield _event("done", {"status": plan.status})
            return
        await asyncio.sleep(STREAM_POLL_SECONDS)


def _cursor(op: EditorOp | None) -> dict | None:
    """Where the agent is working, for the studio's agent cursor: the first item it touched."""
    if op is None or not op.by_agent:
        return None
    touched = json.loads(op.touched or "{}")
    return {"author": op.author, "items": sorted(touched)[:5]}


@style_router.get("", response_model=ApiResponse[list[StylePreference]])
async def list_style(user: CurrentUserDep, session: SessionDep):
    """What the AI has learned about the user's taste from their corrections."""
    beliefs = json.loads((await style.profile(session, user["user_id"])).beliefs or "{}")
    await session.commit()
    rows = []
    for key, belief in sorted(beliefs.items()):
        if key not in style.LABELS or (value := style.value(belief)) is None:
            continue
        label, render = style.LABELS[key]
        conf = style.confidence(belief)
        rows.append(StylePreference(key=key, label=label, value=render(value), confidence=round(conf, 2),
                                    in_use=key in style.resolved(beliefs)))
    return ok(rows)


@style_router.delete("/{key}", response_model=ApiResponse[list[StylePreference]])
async def forget_style(key: str, user: CurrentUserDep, session: SessionDep):
    """Forget one learned preference."""
    await style.forget(session, user["user_id"], key)
    return await list_style(user, session)


@sounds_router.get("", response_model=ApiResponse[SoundSearchResponse])
async def search_sounds(_: CurrentUserDep, q: str = "", page: int = 1, page_size: int = 50):
    """17.1: the studio's Sounds tab searches Clipnera's own library instead of Freesound."""
    from motion.sound import manifest

    words = [w for w in q.lower().split() if w]
    found = []
    for name, entry in sorted(manifest().items()):
        tags = SOUND_TAGS.get(name, [name])
        haystack = " ".join([name.replace("_", " "), *tags])
        if all(w in haystack for w in words):
            found.append(LibrarySound(id=name, name=name.replace("_", " ").title(), tags=tags,
                                      seconds=float(entry.get("seconds", 0)), url=f"/static/sfx/{entry['file']}",
                                      licence="Clipnera library (cleared for commercial use)"))
    page, page_size = max(1, page), min(100, max(1, page_size))
    start = (page - 1) * page_size
    return ok(SoundSearchResponse(results=found[start:start + page_size], count=len(found),
                                  has_more=start + page_size < len(found)))


def _render_status(render) -> RenderStatus:
    return RenderStatus(id=render.id, status=render.status, stage=render.stage, version=render.version,
                        download_url=server_render.download_url(render), error=render.error)


@renders_router.post("/{project_id}/renders", response_model=ApiResponse[RenderStatus])
async def start_render(project_id: str, user: CurrentUserDep, session: SessionDep):
    """17.2: render the saved project at full size on the server."""
    return ok(_render_status(await server_render.start(session, user["user_id"], project_id)))


@renders_router.get("/{project_id}/renders/{render_id}", response_model=ApiResponse[RenderStatus])
async def render_status(project_id: str, render_id: str, user: CurrentUserDep, session: SessionDep):
    return ok(_render_status(await server_render.get(session, user["user_id"], render_id)))


@admin_router.get("/metrics", response_model=ApiResponse[RolloutMetrics])
async def metrics(session: SessionDep, days: int = 7):
    """Turns, cost per turn and undo rate, to watch a rollout (TODO 18.1.3)."""
    return ok(RolloutMetrics(**await rollout_metrics(session, max(1, min(90, days)))))
