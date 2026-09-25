from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from auth.dependencies import CurrentUserDep
from core.rate_limit import no_rate_limit
from core.responses import ApiResponse, ok
from notifications.dependencies import InboxServiceDep, NotificationServiceDep
from notifications.schema import (
    InAppNotificationListResponse,
    NotificationResponse,
    SendEmailRequest,
    SendSMSRequest,
)
from notifications.service import notification_event_stream

notification = APIRouter(prefix="/notifications", tags=["notifications"])


@notification.post("/email", response_model=NotificationResponse)
async def send_email(data: SendEmailRequest, service: NotificationServiceDep):
    message_id = service.send_email(to=data.to, subject=data.subject, body=data.body, sender=data.sender)
    return NotificationResponse(id=message_id, channel="email")


@notification.post("/sms", response_model=NotificationResponse)
async def send_sms(data: SendSMSRequest, service: NotificationServiceDep):
    message_id = service.send_sms(to=data.to, message=data.message)
    return NotificationResponse(id=message_id, channel="sms")


@notification.get("", response_model=ApiResponse[InAppNotificationListResponse])
async def list_notifications(
    user: CurrentUserDep, service: InboxServiceDep, limit: int = Query(30, ge=1, le=100)
):
    return ok(await service.inbox(user["user_id"], limit))


@notification.post("/read-all", response_model=ApiResponse[InAppNotificationListResponse])
async def mark_all_read(user: CurrentUserDep, service: InboxServiceDep):
    return ok(await service.mark_all_read(user["user_id"]), message="Notifications marked as read")


@notification.delete("", response_model=ApiResponse[InAppNotificationListResponse])
async def clear_notifications(user: CurrentUserDep, service: InboxServiceDep):
    return ok(await service.clear(user["user_id"]), message="Notifications cleared")


@notification.get("/stream")
@no_rate_limit
async def stream_notifications(request: Request, user: CurrentUserDep):
    """Server-sent events: one ``notification`` event per InAppNotificationResponse
    as it is created. Missed events are recovered from GET /notifications."""
    return StreamingResponse(
        notification_event_stream(user["user_id"], request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
