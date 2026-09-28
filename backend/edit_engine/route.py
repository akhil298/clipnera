from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

import edit_engine.jobs  # noqa: F401 -- registers the analyse, plan and render job handlers
from auth.dependencies import CurrentUserDep, get_current_admin
from core.database import get_db
from core.responses import ApiResponse, ok
from edit_engine.schema import (
    EditChangesRequest,
    EditChatRequest,
    EditCreateRequest,
    EditLimitsResponse,
    EditResponse,
    EditSourcesCompleteRequest,
    EditSourcesInitRequest,
    EditSourcesInitResponse,
    EditSummary,
    MusicStatusRequest,
    MusicTrackResponse,
)
from edit_engine.service import EditService, MusicLibraryService
from feature_flags.dependencies import require_flag
from feature_flags.registry import REEL_EDITOR
from auth.model import User

edits = APIRouter(prefix="/edits", tags=["edits"], dependencies=[Depends(require_flag(REEL_EDITOR))])
# The library stays open to admins while the feature is off, so it can be filled before launch.
admin_music = APIRouter(prefix="/admin/music", tags=["admin"], dependencies=[Depends(get_current_admin)])


async def get_edit_service(session: Annotated[AsyncSession, Depends(get_db)]) -> EditService:
    return EditService(session)


async def get_music_service(session: Annotated[AsyncSession, Depends(get_db)]) -> MusicLibraryService:
    return MusicLibraryService(session)


EditServiceDep = Annotated[EditService, Depends(get_edit_service)]
MusicServiceDep = Annotated[MusicLibraryService, Depends(get_music_service)]


@edits.get("/limits", response_model=ApiResponse[EditLimitsResponse])
async def edit_limits(user: CurrentUserDep, service: EditServiceDep):
    """What the caller's plan allows: footage minutes, files, reel length, output size."""
    return ok(await service.limits(user["user_id"]))


@edits.post("", response_model=ApiResponse[EditResponse])
async def create_edit(data: EditCreateRequest, user: CurrentUserDep, service: EditServiceDep):
    return ok(await service.create(user["user_id"], data))


@edits.get("", response_model=ApiResponse[list[EditSummary]])
async def list_edits(user: CurrentUserDep, service: EditServiceDep):
    return ok(await service.list(user["user_id"]))


@edits.get("/{edit_id}", response_model=ApiResponse[EditResponse])
async def get_edit(edit_id: str, user: CurrentUserDep, service: EditServiceDep):
    return ok(await service.get(user["user_id"], edit_id))


@edits.post("/{edit_id}/sources/init", response_model=ApiResponse[EditSourcesInitResponse])
async def init_sources(edit_id: str, data: EditSourcesInitRequest, user: CurrentUserDep, service: EditServiceDep):
    """Signed upload URLs for videos, photos and a voiceover; the browser PUTs straight to S3."""
    return ok(await service.init_sources(user["user_id"], edit_id, data))


@edits.post("/{edit_id}/sources/complete", response_model=ApiResponse[EditResponse])
async def complete_sources(edit_id: str, data: EditSourcesCompleteRequest, user: CurrentUserDep, service: EditServiceDep):
    return ok(await service.complete_sources(user["user_id"], edit_id, data))


@edits.post("/{edit_id}/analyze", response_model=ApiResponse[EditResponse])
async def analyze_edit(edit_id: str, user: CurrentUserDep, service: EditServiceDep):
    """Analyse the footage and plan the reel (poll until status is planned). Free: credits are taken at render."""
    return ok(await service.analyze(user["user_id"], edit_id))


@edits.post("/{edit_id}/plan", response_model=ApiResponse[EditResponse])
async def replan_edit(edit_id: str, user: CurrentUserDep, service: EditServiceDep):
    """Ask the director for a fresh plan, keeping the analysis."""
    return ok(await service.replan(user["user_id"], edit_id))


@edits.post("/{edit_id}/changes", response_model=ApiResponse[EditResponse])
async def change_edit(edit_id: str, data: EditChangesRequest, user: CurrentUserDep, service: EditServiceDep):
    """Change the plan (hook, music, look, lines, length...) and get the recompiled timeline."""
    return ok(await service.apply_changes(user["user_id"], edit_id, data.changes))


@edits.post("/{edit_id}/chat", response_model=ApiResponse[EditResponse])
async def chat_edit(edit_id: str, data: EditChatRequest, user: CurrentUserDep, service: EditServiceDep):
    """Change the plan by describing the change, e.g. "make the hook punchier"."""
    return ok(await service.chat(user["user_id"], edit_id, data.message))


@edits.post("/{edit_id}/render", response_model=ApiResponse[EditResponse])
async def render_edit(edit_id: str, user: CurrentUserDep, service: EditServiceDep):
    """Charge the render and queue it (poll until status is done); refunded if it fails."""
    return ok(await service.render(user["user_id"], edit_id))


@admin_music.get("", response_model=ApiResponse[list[MusicTrackResponse]])
async def list_music(service: MusicServiceDep):
    return ok(await service.list())


@admin_music.post("", response_model=ApiResponse[MusicTrackResponse])
async def add_music(
    service: MusicServiceDep,
    admin: Annotated[User, Depends(get_current_admin)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=300)],
    artist: Annotated[str, Form(min_length=1, max_length=300)],
    source: Annotated[str, Form()],
    source_url: Annotated[str, Form(min_length=8, max_length=1000)],
    source_id: Annotated[str, Form(min_length=1, max_length=200)],
    licence: Annotated[str, Form()],
    mood: Annotated[str, Form()],
    commercial_ok: Annotated[bool, Form()],
    edit_ok: Annotated[bool, Form()],
    energy: Annotated[float, Form(ge=0, le=1)] = 0.5,
    bpm: Annotated[float | None, Form(ge=40, le=240)] = None,
    credit_text: Annotated[str, Form(max_length=500)] = "",
):
    """Add a free-licence track with its licence record; refused unless the licence allows commercial use and editing."""
    fields = {"title": title, "artist": artist, "source": source, "source_url": source_url, "source_id": source_id,
              "licence": licence, "mood": mood, "commercial_ok": commercial_ok, "edit_ok": edit_ok, "energy": energy,
              "bpm": bpm, "credit_text": credit_text.strip()}
    return ok(await service.add(admin.id, await file.read(), file.filename or "track.mp3", fields))


@admin_music.post("/{track_id}/status", response_model=ApiResponse[MusicTrackResponse])
async def set_music_status(track_id: str, data: MusicStatusRequest, service: MusicServiceDep):
    """Pull a track (it stops being picked, and renders drop it) or put it back live."""
    return ok(await service.set_status(track_id, data.status))
