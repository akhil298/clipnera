"""Database access for in-app notifications. Every query is scoped to one user."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.model import Notification, NotificationKind


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: str,
        kind: NotificationKind,
        title: str,
        message: str,
        project_id: str | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id, kind=kind.value, title=title, message=message, project_id=project_id
        )
        self._session.add(notification)
        await self._session.commit()
        return notification

    async def list_recent(self, user_id: str, limit: int) -> list[Notification]:
        result = await self._session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def mark_all_read(self, user_id: str) -> None:
        await self._session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.utcnow())
        )
        await self._session.commit()

    async def delete_all(self, user_id: str) -> None:
        await self._session.execute(delete(Notification).where(Notification.user_id == user_id))
        await self._session.commit()
