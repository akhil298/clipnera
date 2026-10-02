from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep
from core.database import get_db
from core.responses import ApiResponse, ok
from editor.schema import EditorOpsRequest, EditorOpsResponse, EditorProjectCreate, EditorProjectResponse, EditorProjectSummary
from editor.service import EditorService
from feature_flags.dependencies import require_flag
from feature_flags.registry import AGENT_EDITOR

editor = APIRouter(prefix="/editor", tags=["editor"], dependencies=[Depends(require_flag(AGENT_EDITOR))])


async def get_editor_service(session: Annotated[AsyncSession, Depends(get_db)]) -> EditorService:
    return EditorService(session)


EditorServiceDep = Annotated[EditorService, Depends(get_editor_service)]


@editor.post("/projects", response_model=ApiResponse[EditorProjectResponse])
async def create_project(data: EditorProjectCreate, user: CurrentUserDep, service: EditorServiceDep):
    return ok(await service.create(user["user_id"], data))


@editor.post("/projects/from-reel/{edit_id}", response_model=ApiResponse[EditorProjectResponse])
async def open_reel(edit_id: str, user: CurrentUserDep, service: EditorServiceDep):
    """Open a footage reel's current edit in the editor as a new project."""
    return ok(await service.import_reel(user["user_id"], edit_id))


@editor.get("/projects", response_model=ApiResponse[list[EditorProjectSummary]])
async def list_projects(user: CurrentUserDep, service: EditorServiceDep):
    return ok(await service.list(user["user_id"]))


@editor.get("/projects/{project_id}", response_model=ApiResponse[EditorProjectResponse])
async def get_project(project_id: str, user: CurrentUserDep, service: EditorServiceDep):
    return ok(await service.get(user["user_id"], project_id))


@editor.post("/projects/{project_id}/ops", response_model=ApiResponse[EditorOpsResponse])
async def apply_ops(project_id: str, data: EditorOpsRequest, user: CurrentUserDep, service: EditorServiceDep):
    """Apply a batch of Timeline operations; 409 STALE_VERSION if the project moved on since base_version."""
    return ok(await service.apply(user["user_id"], project_id, data.base_version, data.ops))
