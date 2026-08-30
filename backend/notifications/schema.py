from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator
from enum import Enum

from notifications.service import NotificationType


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    sender: Optional[str] = None

    @field_validator("to")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email address")
        return value


class SendSMSRequest(BaseModel):
    to: str
    message: str


class NotificationResponse(BaseModel):
    id: str
    channel: NotificationChannel
    status: str = "sent"
