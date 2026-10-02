"""Editor projects: create, open a reel in the editor, read, and apply operations."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import CustomException
from edit_engine.model import EditProject
from editor.model import EditorOp, EditorProject
from editor.ops import Op, apply_ops
from editor.reel_adapter import from_reel
from editor.schema import EditorOpsResponse, EditorProjectCreate, EditorProjectResponse, EditorProjectSummary
from editor.timeline import Timeline, Track
from video_processor.geometry import output_dimensions

MAX_PROJECTS_LISTED = 100


class EditorService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: str, request: EditorProjectCreate) -> EditorProjectResponse:
        width, height = output_dimensions(request.aspect)
        timeline = Timeline(width=width, height=height, tracks=[Track(id="v1", kind="video")])
        return await self._add(user_id, request.title.strip(), timeline)

    async def import_reel(self, user_id: str, edit_id: str) -> EditorProjectResponse:
        """Open a footage reel's current edit as a new editor project; the reel itself is left as it is."""
        edit = await self._session.scalar(
            select(EditProject).where(EditProject.id == edit_id, EditProject.user_id == user_id)
        )
        if edit is None:
            raise CustomException(message="Reel not found.", code="NOT_FOUND", status_code=404)
        compiled = json.loads(edit.timeline or "{}")
        if not compiled.get("picture"):
            raise CustomException(message="This reel has no edit to open yet.", code="NOT_READY", status_code=409)
        timeline = from_reel(compiled, json.loads(edit.sources), caption_style=edit.caption_style,
                             language=edit.language, size=(compiled["width"], compiled["height"]))
        return await self._add(user_id, edit.title, timeline)

    async def list(self, user_id: str) -> list[EditorProjectSummary]:
        rows = (await self._session.execute(
            select(EditorProject).where(EditorProject.user_id == user_id)
            .order_by(EditorProject.updated_at.desc()).limit(MAX_PROJECTS_LISTED)
        )).scalars().all()
        return [_summary(row, _load(row)) for row in rows]

    async def get(self, user_id: str, project_id: str) -> EditorProjectResponse:
        project = await self._project(user_id, project_id)
        return _response(project, _load(project))

    async def apply(self, user_id: str, project_id: str, base_version: int, ops: Sequence[Op],
                    author: str = "user") -> EditorOpsResponse:
        """Apply one batch of operations made against ``base_version``, as one new version."""
        project = await self._project(user_id, project_id, lock=True)
        try:
            if base_version != project.version:
                raise CustomException(
                    message="This project changed since you loaded it. Reload it and try again.",
                    code="STALE_VERSION", status_code=409, extra={"version": project.version},
                )
            timeline = apply_ops(_load(project), ops)
        except CustomException:
            # Release the row lock: an agent turn keeps using this session after a refused edit.
            await self._session.rollback()
            raise
        project.version += 1
        project.timeline = _dump(timeline)
        self._session.add(EditorOp(
            project_id=project.id, version=project.version, author=author,
            ops=json.dumps([op.model_dump(mode="json", exclude_defaults=True) for op in ops]),
        ))
        await self._session.commit()
        return EditorOpsResponse(version=project.version, timeline=timeline)

    async def _add(self, user_id: str, title: str, timeline: Timeline) -> EditorProjectResponse:
        project = EditorProject(user_id=user_id, title=title, timeline=_dump(timeline))
        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        return _response(project, timeline)

    async def _project(self, user_id: str, project_id: str, lock: bool = False) -> EditorProject:
        query = select(EditorProject).where(EditorProject.id == project_id, EditorProject.user_id == user_id)
        project = await self._session.scalar(query.with_for_update() if lock else query)
        if project is None:
            raise CustomException(message="Project not found.", code="NOT_FOUND", status_code=404)
        return project


def _load(project: EditorProject) -> Timeline:
    return Timeline.model_validate_json(project.timeline)


def _dump(timeline: Timeline) -> str:
    return timeline.model_dump_json(exclude_defaults=True)


def _summary(project: EditorProject, timeline: Timeline) -> EditorProjectSummary:
    return EditorProjectSummary(
        id=project.id, title=project.title, version=project.version,
        duration_s=round(timeline.duration / timeline.fps, 2),
        created_at=project.created_at, updated_at=project.updated_at,
    )


def _response(project: EditorProject, timeline: Timeline) -> EditorProjectResponse:
    return EditorProjectResponse(**_summary(project, timeline).model_dump(), timeline=timeline)
