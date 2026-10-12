from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep
from core.database import get_db
from core.responses import ApiResponse, ok
from editor.schema import (
    EditorAssetInitRequest,
    EditorAssetUpload,
    EditorOpsRequest,
    EditorOpsResponse,
    EditorProjectCreate,
    EditorProjectResponse,
    EditorProjectSummary,
    MediaAnalysisResponse,
)
from editor.service import EditorService
from feature_flags.dependencies import require_user_flag
from usage.context import llm_scope
from brain.schema import TurnRequest, TurnResult
from brain.turns import handle_turn
from feature_flags.registry import AGENT_EDITOR
import understanding.jobs  # noqa: F401 -- registers the media understanding job handler

editor = APIRouter(prefix="/editor", tags=["editor"], dependencies=[Depends(require_user_flag(AGENT_EDITOR))])


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


@editor.post("/projects/{project_id}/assets/init", response_model=ApiResponse[EditorAssetUpload])
async def init_asset(project_id: str, data: EditorAssetInitRequest, user: CurrentUserDep, service: EditorServiceDep):
    """A signed URL to PUT one media file to; add it to the Timeline with an ``add_asset`` op once it is up."""
    return ok(await service.init_asset(user["user_id"], project_id, data))


@editor.post("/projects/{project_id}/undo", response_model=ApiResponse[EditorOpsResponse])
async def undo(project_id: str, user: CurrentUserDep, service: EditorServiceDep):
    """Undo the last change still in effect (an agent step undoes as one); 409 NOTHING_TO_UNDO at the start."""
    return ok(await service.undo(user["user_id"], project_id))


@editor.post("/projects/{project_id}/redo", response_model=ApiResponse[EditorOpsResponse])
async def redo(project_id: str, user: CurrentUserDep, service: EditorServiceDep):
    return ok(await service.redo(user["user_id"], project_id))


@editor.post("/projects/{project_id}/steps/{step_id}/undo", response_model=ApiResponse[EditorOpsResponse])
async def undo_step(project_id: str, step_id: str, user: CurrentUserDep, service: EditorServiceDep):
    """Undo everything one AI step changed, even with later edits on top."""
    return ok(await service.undo_step(user["user_id"], project_id, step_id))


@editor.get("/projects/{project_id}/analysis", response_model=ApiResponse[list[MediaAnalysisResponse]])
async def list_analyses(project_id: str, user: CurrentUserDep, service: EditorServiceDep):
    """How far the AI has got understanding each of the project's assets."""
    return ok(await service.analyses(user["user_id"], project_id))


@editor.post("/projects/{project_id}/analysis/{asset_id}/retry", response_model=ApiResponse[MediaAnalysisResponse])
async def retry_analysis(project_id: str, asset_id: str, user: CurrentUserDep, service: EditorServiceDep):
    """Run a failed analysis again."""
    return ok(await service.retry_analysis(user["user_id"], project_id, asset_id))


@editor.post("/projects/{project_id}/turns", response_model=ApiResponse[TurnResult])
async def take_turn(project_id: str, data: TurnRequest, user: CurrentUserDep, service: EditorServiceDep):
    """One prompt from the studio's AI chat: an edit, an answer, a question back, or a plan."""
    # Not charged to a pipeline project: llm_usage.project_id points at video projects.
    with llm_scope(user_id=user["user_id"], step="editor_turn"):
        result = await handle_turn(service, user["user_id"], project_id, data.prompt, selection=data.selection,
                                   playhead=data.playhead, recent_turns=data.recent_turns)
    return ok(result)
