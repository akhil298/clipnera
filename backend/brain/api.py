"""/editor/plans: the plan card's API (TODO 10.1, 11.4, 11.5). Responses mirrored in frontend/lib/api.ts."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import brain.execute  # noqa: F401 -- registers the plan execution job handler
from auth.dependencies import CurrentUserDep
from brain import library, plans
from brain.model import EditPlan, PlanStepRow
from brain import style
from brain import preview, server_render, voice
from auth.dependencies import get_current_admin
from brain.metrics import rollout_metrics
from brain.schema import (
    BrollAddRequest, BrollAdded, CaptionStyleOption, LibraryBroll, LibraryMusic, MusicAddRequest, MusicAdded, LibraryGraphic, LibrarySound, LookOption, PlanCard, PlanPatch, ProjectPreview, RenderStatus, RolloutMetrics,
    SoundSearchResponse, StylePreference, VoiceText,
)
from core.database import AsyncSessionLocal, get_db
from core.responses import ApiResponse, ok, sse
from editor.model import EditorOp, EditorProject
from editor.service import EditorService
from edit_engine.looks import LOOK_LABELS, LOOKS
from feature_flags.dependencies import require_user_flag
from feature_flags.registry import AGENT_EDITOR

router = APIRouter(prefix="/editor/plans", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
style_router = APIRouter(prefix="/editor/style", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
renders_router = APIRouter(prefix="/editor/projects", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
admin_router = APIRouter(prefix="/admin/ai-editor", tags=["admin"], dependencies=[Depends(get_current_admin)])
voice_router = APIRouter(prefix="/editor/voice", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
looks_router = APIRouter(prefix="/editor/looks", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
captions_router = APIRouter(prefix="/editor/caption-styles", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
music_router = APIRouter(prefix="/editor/music", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
editor_broll_router = APIRouter(prefix="/editor/broll", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
graphics_router = APIRouter(prefix="/editor/graphics", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
sounds_router = APIRouter(prefix="/editor/sounds", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])
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
                yield sse("agent.step", {"step_id": row.step_id, "status": row.status, "note": row.note})
        if version_seen is not None and version != version_seen:
            yield sse("op.applied", {"version": version, "cursor": cursor})
        version_seen = version
        if card != last_card:
            last_card = card
            yield sse("plan.updated", card)
        if plan.status in plans.FINAL:
            yield sse("done", {"status": plan.status})
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
    """The studio's Sounds tab: Clipnera's own library, the same shelf the AI picks from."""
    found = [LibrarySound(id=sound.id, name=sound.name, tags=list(sound.tags), seconds=sound.seconds, url=sound.url,
                          licence=sound.licence, category=sound.category) for sound in library.search_sounds(q)]
    page, page_size = max(1, page), min(100, max(1, page_size))
    start = (page - 1) * page_size
    return ok(SoundSearchResponse(results=found[start:start + page_size], count=len(found),
                                  has_more=start + page_size < len(found)))


@graphics_router.get("", response_model=ApiResponse[list[LibraryGraphic]])
async def list_graphics(_: CurrentUserDep):
    """The studio's graphics shelf, the same one the AI picks from and the export draws."""
    return ok([LibraryGraphic(id=g.id, name=g.name, seconds=g.duration, moods=list(g.moods),
                              url=f"{library.GRAPHICS_URL}/{g.video.name}")
               for g in library.graphics().values()])


@editor_broll_router.get("", response_model=ApiResponse[list[LibraryBroll]])
async def search_broll(_: CurrentUserDep, q: str = "", limit: int = 40):
    """The editor's public-domain B-roll shelf, the same one the AI picks from."""
    return ok([LibraryBroll(id=s.id, title=s.title, category=s.category, topic=s.topic, seconds=s.seconds, url=s.url,
                            licence=s.licence, credit=s.credit) for s in library.search_broll(q, max(1, min(limit, 100)))])


@editor_broll_router.post("/add", response_model=ApiResponse[BrollAdded])
async def add_broll(data: BrollAddRequest, user: CurrentUserDep, session: SessionDep):
    """Copy a shelf shot into the project's storage, for an ``add_asset`` and an overlay clip."""
    return ok(await library.broll_added(EditorService(session), user["user_id"], data.project_id, data.id))


@music_router.get("", response_model=ApiResponse[list[LibraryMusic]])
async def list_music(_: CurrentUserDep, q: str = ""):
    """Clipnera's own music beds, the same shelf the AI picks from."""
    return ok([LibraryMusic(id=t.id, name=t.name, mood=t.mood, tags=list(t.tags), bpm=t.bpm, seconds=t.seconds, url=t.url,
                            licence=t.licence) for t in library.search_music(q)])


@music_router.post("/add", response_model=ApiResponse[MusicAdded])
async def add_music(data: MusicAddRequest, user: CurrentUserDep, session: SessionDep):
    """Copy a shelf track into the project's storage, for an ``add_asset`` and the music track."""
    return ok(await library.music_added(EditorService(session), user["user_id"], data.project_id, data.id))


@voice_router.post("", response_model=ApiResponse[VoiceText])
async def voice_note(_: CurrentUserDep, audio: UploadFile = File(...), seconds: float = Form(..., gt=0)):
    """Transcribes a short voice note from the studio chat."""
    data = await audio.read(voice.MAX_BYTES + 1)
    return ok(VoiceText(text=await voice.transcribe(data, audio.content_type or "", seconds)))


@looks_router.get("", response_model=ApiResponse[list[LookOption]])
async def list_looks(_: CurrentUserDep):
    """The colour looks the server render can give a project."""
    return ok([LookOption(id=look, label=LOOK_LABELS.get(look, look)) for look in LOOKS])


@captions_router.get("", response_model=ApiResponse[list[CaptionStyleOption]])
async def list_caption_styles(_: CurrentUserDep):
    """The caption styles the studio can pick, with what each looks like."""
    return ok(preview.caption_styles())


@renders_router.get("/{project_id}/preview", response_model=ApiResponse[ProjectPreview])
async def project_preview(project_id: str, user: CurrentUserDep, session: SessionDep):
    """What the server render will draw over the picture: captions, titles, sound cues and the look."""
    service = EditorService(session)
    project = await service.get(user["user_id"], project_id)
    muds = (await service.media(user["user_id"], project_id)).muds
    return ok(preview.preview(project.timeline, muds, project.version))


@renders_router.post("/{project_id}/renders", response_model=ApiResponse[RenderStatus])
async def start_render(project_id: str, user: CurrentUserDep, session: SessionDep):
    """17.2: render the saved project at full size on the server."""
    return ok(server_render.status(await server_render.start(session, user["user_id"], project_id)))


@renders_router.get("/{project_id}/renders/{render_id}", response_model=ApiResponse[RenderStatus])
async def render_status(project_id: str, render_id: str, user: CurrentUserDep, session: SessionDep):
    return ok(server_render.status(await server_render.get(session, user["user_id"], render_id)))


@admin_router.get("/metrics", response_model=ApiResponse[RolloutMetrics])
async def metrics(session: SessionDep, days: int = 7):
    """Turns, cost per turn and undo rate, to watch a rollout (TODO 18.1.3)."""
    return ok(RolloutMetrics(**await rollout_metrics(session, max(1, min(90, days)))))
