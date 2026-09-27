from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from notifications.model import NotificationKind


class InAppNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: NotificationKind
    title: str
    message: str
    project_id: Optional[str] = None
    read_at: Optional[datetime] = None
    created_at: datetime


class InAppNotificationListResponse(BaseModel):
    notifications: list[InAppNotificationResponse]
