from __future__ import annotations

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from clip.model import VideoProject, ProjectStatus
from core.logging_config import get_logger

log = get_logger(__name__)


class ClipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_project(
        self,
        user_id: str,
        title: str,
        source_type: str,
        source_url: str | None = None,
        status: ProjectStatus = ProjectStatus.PENDING,
    ) -> VideoProject:
        project = VideoProject(
            user_id=user_id,
            title=title,
            source_type=source_type,
            source_url=source_url,
            status=status,
        )
        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def get_project(self, project_id: str, user_id: str) -> VideoProject | None:
        stmt = select(VideoProject).where(
            VideoProject.id == project_id,
            VideoProject.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_project_status(self, project_id: str, status: ProjectStatus) -> None:
        stmt = select(VideoProject).where(VideoProject.id == project_id)
        result = await self._session.execute(stmt)
        project = result.scalar_one_or_none()
        if project:
            project.status = status
            await self._session.commit()

    async def update_project_s3(
        self, project_id: str, s3_key: str, s3_bucket: str, presigned_url: str,
        file_size: int, duration: int, status: ProjectStatus, local_path: str | None = None
    ) -> None:
        stmt = select(VideoProject).where(VideoProject.id == project_id)
        result = await self._session.execute(stmt)
        project = result.scalar_one_or_none()
        if project:
            project.s3_key = s3_key
            project.s3_bucket = s3_bucket
            project.presigned_url = presigned_url
            project.file_size = file_size
            project.duration_seconds = duration
            project.status = status
            if local_path is not None:
                project.local_path = local_path
            await self._session.commit()

    async def list_projects(self, user_id: str) -> list[VideoProject]:
        stmt = (
            select(VideoProject)
            .where(VideoProject.user_id == user_id)
            .order_by(desc(VideoProject.created_at))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_project(self, project_id: str, user_id: str) -> bool:
        stmt = select(VideoProject).where(
            VideoProject.id == project_id,
            VideoProject.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            return False
        await self._session.delete(project)
        await self._session.commit()
        return True
