from __future__ import annotations

from typing import Any
from enum import Enum

from clients.services.email import EmailClient
from clients.services.sms import SMSClient
from core.exceptions import CustomException


class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"


class NotificationService:
    """High-level notification service — send emails and SMS."""

    def __init__(self) -> None:
        self._email = EmailClient()
        self._sms = SMSClient()

    def send_email(self, to: str, subject: str, body: str, sender: str | None = None) -> str:
        return self._email.send(to=to, subject=subject, body=body, sender=sender)

    def send_sms(self, to: str, message: str) -> str:
        return self._sms.send(to=to, message=message)

    def send(self, type: NotificationType, **kwargs: Any) -> str:
        if type == NotificationType.EMAIL:
            return self.send_email(**kwargs)
        if type == NotificationType.SMS:
            return self.send_sms(**kwargs)
        raise CustomException(
            message=f"Unsupported notification type: {type}",
            code="INVALID_NOTIFICATION_TYPE",
            status_code=400,
        )
