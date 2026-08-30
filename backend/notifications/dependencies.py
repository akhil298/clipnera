from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from notifications.service import NotificationService


async def get_notification_service() -> NotificationService:
    return NotificationService()


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]

__all__ = ["NotificationService", "NotificationServiceDep", "get_notification_service"]
