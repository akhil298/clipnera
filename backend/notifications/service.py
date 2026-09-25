from __future__ import annotations

from typing import Any
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.services.email import EmailClient
from clients.services.sms import SMSClient
from clip.model import VideoProject
from clip_generation.model import GeneratedClip
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from notifications.broker import broker
from notifications.model import Notification, NotificationKind
from notifications.repository import NotificationRepository
from notifications.schema import InAppNotificationResponse

log = get_logger(__name__)


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
        if self._sms._client is None:
            raise CustomException(
                message="SMS not configured: missing Twilio credentials",
                code="SMS_NOT_CONFIGURED",
                status_code=503,
            )
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

    async def notify_pipeline_complete(
        self,
        user_email: str | None,
        user_phone: str | None,
        project_id: str,
        success: bool,
        clip_count: int | None = None,
        error: str | None = None,
    ) -> None:
        """Send notification when a pipeline finishes (success or failure)."""
        if not user_email and not user_phone:
            return

        if success:
            subject = "Clipnera: Your clips are ready!"
            body = (
                f"Your video processing pipeline has completed successfully.\n\n"
                f"Project ID: {project_id}\n"
                f"Clips generated: {clip_count or 'N/A'}\n\n"
                f"You can view and download your clips in the Clipnera dashboard."
            )
            sms_message = (
                f"Clipnera: {clip_count or '?'} clips ready for project {project_id}. "
                f"View in dashboard."
            )
        else:
            subject = "Clipnera: Pipeline failed"
            body = (
                f"Your video processing pipeline encountered an error.\n\n"
                f"Project ID: {project_id}\n"
                f"Error: {error or 'Unknown error'}\n\n"
                f"Credits have been refunded. Please try again."
            )
            sms_message = f"Clipnera: Pipeline failed for project {project_id}. Credits refunded."

        try:
            if user_email:
                self.send_email(to=user_email, subject=subject, body=body)
        except Exception as exc:
            log.warning(f"Email notification failed: project={project_id} error={exc}")

        try:
            if user_phone:
                self.send_sms(to=user_phone, message=sms_message)
        except Exception as exc:
            log.warning(f"SMS notification failed (SMS may not be configured): project={project_id} error={exc}")


class InboxService:
    """In-app notifications: what the dashboard's snackbar and drawer show."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = NotificationRepository(session)

    async def list_recent(self, user_id: str, limit: int) -> list[Notification]:
        return await self._repo.list_recent(user_id, limit)

    async def mark_all_read(self, user_id: str) -> None:
        await self._repo.mark_all_read(user_id)

    async def clear(self, user_id: str) -> None:
        await self._repo.delete_all(user_id)


async def notify_pipeline_outcome(user_id: str, project_id: str, success: bool, refunded: bool = False) -> None:
    """Record a pipeline's outcome in the user's inbox and push it to their open
    dashboards. Best effort: a failure here never changes the outcome it reports."""
    try:
        async with AsyncSessionLocal() as session:
            title = await session.scalar(select(VideoProject.title).where(VideoProject.id == project_id))
            name = f'"{title}"' if title else "Your video"
            if success:
                clip_count = await session.scalar(
                    select(func.count()).select_from(GeneratedClip).where(GeneratedClip.project_id == project_id)
                )
                kind = NotificationKind.PIPELINE_COMPLETED
                heading = "Your clips are ready"
                message = f"{name} finished processing with {clip_count or 0} clip(s)."
            else:
                kind = NotificationKind.PIPELINE_FAILED
                heading = "Processing failed"
                message = f"{name} could not be processed." + (" Your credits were refunded." if refunded else "")
            notification = await NotificationRepository(session).create(
                user_id, kind, heading, message, project_id=project_id
            )
        broker.publish(user_id, InAppNotificationResponse.model_validate(notification).model_dump(mode="json"))
    except Exception as exc:
        log.warning(f"In-app notification failed: project={project_id} error={type(exc).__name__}")
