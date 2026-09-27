from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from notifications.service import InboxService


async def get_inbox_service(session: Annotated[AsyncSession, Depends(get_db)]) -> InboxService:
    return InboxService(session)


InboxServiceDep = Annotated[InboxService, Depends(get_inbox_service)]

__all__ = [
    "InboxService",
    "InboxServiceDep",
    "get_inbox_service",
]
