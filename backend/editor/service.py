"""Editor projects: create, open a reel in the editor, read, and apply operations."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.services.s3 import S3
from core.config import get_settings
from core.exceptions import CustomException
from core.logging_config import get_logger
from edit_engine.model import EditProject
from editor.history import (
    HUMAN,
    Actor,
    Stacks,
    check_agent_guards,
    check_human_owned,
    check_rebase,
    dump_touched,
    human_owned,
    op_count,
    stacks,
    step_groups,
    touched_of,
)
from editor.model import EditorOp, EditorProject
from editor.ops import STORED_OPS, AddAsset, Applied, Op, apply_tracked
from editor.reel_adapter import from_reel
from editor.schema import (
    EditorAssetInitRequest,
    EditorAssetUpload,
    EditorOpsResponse,
    EditorProjectCreate,
    EditorProjectResponse,
    EditorProjectSummary,
    MediaAnalysisResponse,
)
from editor.timeline import Timeline, TimelineError, Track
from brain.invariants import check_agent_tx
from understanding.service import ProjectMedia, UnderstandingService
from video_processor.geometry import output_dimensions

log = get_logger(__name__)
MAX_PROJECTS_LISTED = 100
URL_TTL_SECONDS = 3600
_EXTENSIONS = {
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm",
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/webm": ".weba", "audio/ogg": ".ogg",
}


def asset_prefix(user_id: str, project_id: str) -> str:
    """Where a project's uploads live; ``add_asset`` accepts no other key, so no one can point at another's file."""
    return f"editor/{user_id}/{project_id}/"


class EditorService:
    def __init__(self, session: AsyncSession, s3: S3 | None = None) -> None:
        self._session = session
        self._s3_client = s3
        self._settings = get_settings()

    @property
    def session(self) -> AsyncSession:
        """The request's database session, for the AI's context (brain/) to read the op log in."""
        return self._session

    @property
    def _s3(self) -> S3:
        # Made on first use: most requests sign nothing.
        if self._s3_client is None:
            self._s3_client = S3()
        return self._s3_client

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
        return self._response(project, _load(project))

    async def recent_items(self, user_id: str, project_id: str, batches: int = 10) -> list[str]:
        """Item ids changed in the last ``batches`` saves, newest first (for "it" and "that")."""
        project = await self._project(user_id, project_id)
        rows = (await self._session.execute(
            select(EditorOp).where(EditorOp.project_id == project.id).order_by(EditorOp.version.desc()).limit(batches)
        )).scalars().all()
        return list(dict.fromkeys(item for row in rows for item in touched_of(row)))

    async def media(self, user_id: str, project_id: str) -> ProjectMedia:
        """The project's media as the AI knows it (understanding/)."""
        project = await self._project(user_id, project_id)
        timeline = _load(project)
        understanding = UnderstandingService(self._session, self._s3_client)
        statuses = {row.asset_id: row.status for row in await understanding.statuses(project.id)}
        return ProjectMedia(fps=timeline.fps, names={a.id: Path(a.key).name for a in timeline.assets.values()},
                            muds=await understanding.muds(project.id), statuses=statuses)

    async def ensure_moments(self, user_id: str, project_id: str) -> None:
        """Pick the strongest moments of the project's footage, for an edit that needs them (understanding/)."""
        project = await self._project(user_id, project_id)
        await UnderstandingService(self._session, self._s3_client).ensure_moments(project.id)

    async def analyses(self, user_id: str, project_id: str) -> list[MediaAnalysisResponse]:
        project = await self._project(user_id, project_id)
        rows = await UnderstandingService(self._session, self._s3_client).statuses(project.id)
        return [MediaAnalysisResponse.model_validate(row, from_attributes=True) for row in rows]

    async def retry_analysis(self, user_id: str, project_id: str, asset_id: str) -> MediaAnalysisResponse:
        project = await self._project(user_id, project_id)
        row = await UnderstandingService(self._session, self._s3_client).retry(project.id, asset_id)
        return MediaAnalysisResponse.model_validate(row, from_attributes=True)

    async def init_asset(self, user_id: str, project_id: str, request: EditorAssetInitRequest) -> EditorAssetUpload:
        """A signed PUT for one file of the project; once it is up, the studio adds it with ``add_asset``."""
        project = await self._project(user_id, project_id)
        suffix = _EXTENSIONS[request.content_type]
        key = f"{asset_prefix(user_id, project.id)}{uuid4().hex}{suffix}"
        url = self._s3.presign_put(self._settings.S3_BUCKET_NAME, key, request.content_type, URL_TTL_SECONDS)
        return EditorAssetUpload(key=key, url=url, content_type=request.content_type)

    async def import_file(self, user_id: str, project_id: str, path: Path, content_type: str) -> str:
        """Copy a file from Clipnera's own shelves into the project's storage; returns its key for ``add_asset``."""
        project = await self._project(user_id, project_id)
        key = f"{asset_prefix(user_id, project.id)}{uuid4().hex}{_EXTENSIONS[content_type]}"
        await asyncio.to_thread(self._s3.upload_file, self._settings.S3_BUCKET_NAME, key, str(path), content_type)
        return key

    async def apply(self, user_id: str, project_id: str, base_version: int, ops: Sequence[Op],
                    actor: Actor = HUMAN) -> EditorOpsResponse:
        """Apply one batch of operations made against ``base_version``, as one new version.

        A batch made against an older version is applied to the current one when no one has
        changed the same fields since (see editor.history); a newer ``base_version`` than the
        project's is refused with STALE_VERSION.
        """
        project = await self._project(user_id, project_id, lock=True)
        try:
            _check_asset_keys(ops, asset_prefix(user_id, project.id))
            if base_version > project.version:
                raise _stale(project)
            # An agent's edit is checked against the whole history; a person's only against what's newer.
            rows = await self._log(project.id, after=None if actor.is_agent else base_version)
            current = _load(project)
            try:
                applied = apply_tracked(current, ops)
            except TimelineError:
                # Made against an older Timeline: say so, so the client reloads rather than gives up.
                if base_version < project.version:
                    raise _stale(project) from None
                raise
            if base_version < project.version:
                check_rebase(applied.touched, [r for r in rows if r.version > base_version], current)
            if actor.is_agent:
                check_human_owned(applied.touched, human_owned(rows), actor, current)
                check_agent_guards(ops, current, applied.timeline, actor,
                                   op_count(rows, step_id=actor.step_id), op_count(rows, turn_id=actor.turn_id))
                muds = await UnderstandingService(self._session, self._s3_client).muds(project.id)
                check_agent_tx(current, applied.timeline, ops, muds,
                               allowed_text=actor.allowed_text if actor.allowed_text is not None else frozenset(),
                               may_resize=actor.may_resize)
        except CustomException:
            # Release the row lock: an agent turn keeps using this session after a refused edit.
            await self._session.rollback()
            raise
        response = await self._commit(project, ops, applied, actor)
        if not actor.is_agent:
            await self._learn(user_id, project.id, current, applied.timeline, ops)
        return response

    async def _learn(self, user_id: str, project_id: str, before: Timeline, after: Timeline, ops: Sequence[Op]) -> None:
        """A person correcting the AI teaches style memory (brain.style); it never fails the save."""
        from brain.style import learn  # The editor works without the AI's modules loaded.

        try:
            await learn(self._session, user_id, project_id, before, after, ops)
        except Exception as exc:  # pragma: no cover - logged, never raised into a save
            await self._session.rollback()
            log.warning("Style memory couldn't learn from an edit: %s", exc)

    async def undo(self, user_id: str, project_id: str) -> EditorOpsResponse:
        """Undo the last change still in effect; an agent step's batches undo together."""
        return await self._revert(user_id, project_id, lambda state: state.undo[-1].versions if state.undo else [],
                                  "undo", "There's nothing to undo.")

    async def redo(self, user_id: str, project_id: str) -> EditorOpsResponse:
        return await self._revert(user_id, project_id, lambda state: state.redo[-1].versions if state.redo else [],
                                  "redo", "There's nothing to redo.")

    async def undo_step(self, user_id: str, project_id: str, step_id: str) -> EditorOpsResponse:
        """Undo every change one agent step made, wherever it sits in the history."""
        return await self._revert(user_id, project_id, lambda state: step_groups(state, step_id),
                                  "undo", "That step has nothing left to undo.")

    async def _revert(self, user_id: str, project_id: str, pick: Callable[[Stacks], list[int]],
                      kind: str, nothing: str) -> EditorOpsResponse:
        project = await self._project(user_id, project_id, lock=True)
        try:
            rows = await self._log(project.id)
            versions = pick(stacks(rows))
            if not versions:
                raise CustomException(message=nothing, code="NOTHING_TO_" + kind.upper(), status_code=409)
            by_version = {row.version: row for row in rows}
            targets = [by_version[v] for v in versions]
            if kind == "undo":
                if any(row.inverse is None for row in targets):
                    raise CustomException(message="That change was made before undo existed and can't be undone.",
                                          code="CANNOT_UNDO", status_code=409)
                ops = [op for row in reversed(targets) for op in STORED_OPS.validate_json(row.inverse)]
            else:
                ops = [op for row in targets for op in STORED_OPS.validate_json(row.ops)]
            try:
                applied = apply_tracked(_load(project), ops)
            except TimelineError as exc:
                raise CustomException(
                    message=f"Later changes are in the way, so this can't be {_DONE[kind]}: {exc.message}",
                    code=kind.upper() + "_CONFLICT", status_code=409,
                ) from exc
        except CustomException:
            await self._session.rollback()
            raise
        return await self._commit(project, ops, applied, HUMAN, kind=kind, targets=versions)

    async def _commit(self, project: EditorProject, ops: Sequence[Any], applied: Applied, actor: Actor,
                      kind: str = "edit", targets: list[int] | None = None) -> EditorOpsResponse:
        project.version += 1
        project.timeline = _dump(applied.timeline)
        self._session.add(EditorOp(
            project_id=project.id, version=project.version, author=actor.author, kind=kind,
            targets=json.dumps(targets) if targets is not None else None,
            step_id=actor.step_id, turn_id=actor.turn_id,
            ops=_dump_ops(ops), inverse=_dump_ops(applied.inverse), touched=dump_touched(applied.touched),
        ))
        await self._session.commit()
        if any(op.op in ("add_asset", "restore_fields") for op in ops):
            await self._understand(project, applied.timeline)
        return EditorOpsResponse(version=project.version, timeline=applied.timeline)

    async def _understand(self, project: EditorProject, timeline: Timeline) -> None:
        """Queue the AI's analysis of assets it hasn't seen; images and media alike (see understanding/)."""
        await UnderstandingService(self._session, self._s3_client).queue(
            project.user_id, project.id, timeline.assets.values())

    async def _log(self, project_id: str, after: int | None = None) -> list[EditorOp]:
        query = select(EditorOp).where(EditorOp.project_id == project_id)
        if after is not None:
            query = query.where(EditorOp.version > after)
        return list((await self._session.execute(query.order_by(EditorOp.version))).scalars().all())

    async def _add(self, user_id: str, title: str, timeline: Timeline) -> EditorProjectResponse:
        project = EditorProject(user_id=user_id, title=title, timeline=_dump(timeline))
        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        await self._understand(project, timeline)
        return self._response(project, timeline)

    def _response(self, project: EditorProject, timeline: Timeline) -> EditorProjectResponse:
        urls = {
            asset.id: self._s3.generate_presigned_url(self._settings.S3_BUCKET_NAME, asset.key, URL_TTL_SECONDS)
            for asset in timeline.assets.values()
        }
        return EditorProjectResponse(**_summary(project, timeline).model_dump(), timeline=timeline, asset_urls=urls)

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


_DONE = {"undo": "undone", "redo": "redone"}


def _dump_ops(ops: Sequence[Any]) -> str:
    return json.dumps([op.model_dump(mode="json", exclude_defaults=True) for op in ops])


def _stale(project: EditorProject) -> CustomException:
    return CustomException(
        message="This project changed since you loaded it. Reload it and try again.",
        code="STALE_VERSION", status_code=409, extra={"version": project.version},
    )


def _check_asset_keys(ops: Sequence[Op], prefix: str) -> None:
    """Only files uploaded to this project may be added to it (a reel's footage comes in through ``import_reel``)."""
    for index, op in enumerate(ops):
        key = op.asset.key if isinstance(op, AddAsset) else None
        if key is not None and not (key.startswith(prefix) and Path(key).suffix in _EXTENSIONS.values()
                                    and ".." not in key):
            raise CustomException(message="That file wasn't uploaded to this project.", code="UNKNOWN_UPLOAD",
                                  status_code=422, extra={"op_index": index})
