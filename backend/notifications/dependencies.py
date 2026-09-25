from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from notifications.service import InboxService, NotificationService


async def get_notification_service() -> NotificationService:
    return NotificationService()


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


async def get_inbox_service(session: Annotated[AsyncSession, Depends(get_db)]) -> InboxService:
    return InboxService(session)


InboxServiceDep = Annotated[InboxService, Depends(get_inbox_service)]

__all__ = [
    "InboxService",
    "InboxServiceDep",
    "NotificationService",
    "NotificationServiceDep",
    "get_inbox_service",
    "get_notification_service",
]
