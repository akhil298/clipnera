from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep
from brain import studio
from core.database import AsyncSessionLocal, get_db
from core.logging_config import get_logger
from core.responses import ApiResponse, ok, sse
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
from brain.schema import AgentError, AgentRequest, AiModels, TurnRequest, TurnResult
from clients.ai.roles import EFFORTS, picked_model, selectable_models
from core.exceptions import CustomException
from brain.turns import handle_turn
from feature_flags.registry import AGENT_EDITOR
import understanding.jobs  # noqa: F401 -- registers the media understanding job handler

log = get_logger(__name__)

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


@editor.get("/models", response_model=ApiResponse[AiModels])
async def list_models(_: CurrentUserDep):
    """The models and reasoning efforts the AI chat offers."""
    models = selectable_models()
    return ok(AiModels(models=models, default_model=models[0], efforts=list(EFFORTS)))


@editor.post("/projects/{project_id}/turns", response_model=ApiResponse[TurnResult])
async def take_turn(project_id: str, data: TurnRequest, user: CurrentUserDep, service: EditorServiceDep):
    """One prompt from the studio's AI chat: an edit, an answer, a question back, or a plan."""
    _check_model(data.model)
    # Not charged to a pipeline project: llm_usage.project_id points at video projects.
    try:
        with llm_scope(user_id=user["user_id"], step="editor_turn"), picked_model(data.model, data.effort):
            result = await handle_turn(service, user["user_id"], project_id, data.prompt, selection=data.selection,
                                       playhead=data.playhead, recent_turns=data.recent_turns,
                                       questions_asked=data.questions_asked, auto=data.auto)
    except httpx.HTTPError as exc:
        # As a handled error, so the browser can read it (an unhandled one comes back without CORS headers).
        raise CustomException(message=_unavailable(data.model), code="AI_UNAVAILABLE", status_code=502) from exc
    return ok(result)


@editor.post("/projects/{project_id}/agent")
async def agent_turn(project_id: str, data: AgentRequest, user: CurrentUserDep, service: EditorServiceDep):
    """One prompt for the studio agent (brain/studio.py), answered as server-sent events while it
    works: text, tool, tool_done, edit, undone, ui, todos, ask, plan, render, result, then done or error."""
    _check_model(data.model)
    await service.get(user["user_id"], project_id)  # A missing project is a 404, not a broken stream.
    return StreamingResponse(_agent_events(user["user_id"], project_id, data), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _agent_events(user_id: str, project_id: str, data: AgentRequest) -> AsyncIterator[str]:
    # Its own session: the request's closes before a streamed body is sent.
    async with AsyncSessionLocal() as session:
        with llm_scope(user_id=user_id, step="editor_turn"), picked_model(data.model, data.effort):
            try:
                async for name, payload in studio.stream(EditorService(session), user_id, project_id, data):
                    yield sse(name, payload.model_dump(mode="json"))
            except httpx.HTTPError:
                yield sse("error", AgentError(message=_unavailable(data.model)).model_dump())
            except CustomException as exc:
                yield sse("error", AgentError(message=exc.message).model_dump())
            except Exception:
                log.exception("Studio agent turn failed: project=%s", project_id)
                yield sse("error", AgentError(message="Something went wrong. Try again.").model_dump())


def _check_model(model: str | None) -> None:
    if model and model not in selectable_models():
        raise CustomException(message=f"The AI can't use {model}.", code="UNKNOWN_MODEL", status_code=422)


def _unavailable(model: str | None) -> str:
    return f"The AI model ({model or 'the default model'}) didn't answer. Try again, or pick another model."
