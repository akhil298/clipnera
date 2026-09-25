import asyncio
import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from auth.dependencies import CurrentUserDep
from core.rate_limit import no_rate_limit
from core.responses import ApiResponse, ok
from notifications.broker import broker
from notifications.dependencies import InboxServiceDep, NotificationServiceDep
from notifications.schema import (
    InAppNotificationListResponse,
    InAppNotificationResponse,
    NotificationResponse,
    SendEmailRequest,
    SendSMSRequest,
)

notification = APIRouter(prefix="/notifications", tags=["notifications"])

# Under typical proxy idle timeouts, so an open stream is never cut as idle.
KEEPALIVE_SECONDS = 25


@notification.post("/email", response_model=NotificationResponse)
async def send_email(data: SendEmailRequest, service: NotificationServiceDep):
    message_id = service.send_email(to=data.to, subject=data.subject, body=data.body, sender=data.sender)
    return NotificationResponse(id=message_id, channel="email")


@notification.post("/sms", response_model=NotificationResponse)
async def send_sms(data: SendSMSRequest, service: NotificationServiceDep):
    message_id = service.send_sms(to=data.to, message=data.message)
    return NotificationResponse(id=message_id, channel="sms")


async def _inbox(service: InboxServiceDep, user_id: str, limit: int = 30) -> InAppNotificationListResponse:
    rows = await service.list_recent(user_id, limit)
    return InAppNotificationListResponse(
        notifications=[InAppNotificationResponse.model_validate(row) for row in rows]
    )


@notification.get("", response_model=ApiResponse[InAppNotificationListResponse])
async def list_notifications(
    user: CurrentUserDep, service: InboxServiceDep, limit: int = Query(30, ge=1, le=100)
):
    return ok(await _inbox(service, user["user_id"], limit))


@notification.post("/read-all", response_model=ApiResponse[InAppNotificationListResponse])
async def mark_all_read(user: CurrentUserDep, service: InboxServiceDep):
    await service.mark_all_read(user["user_id"])
    return ok(await _inbox(service, user["user_id"]), message="Notifications marked as read")


@notification.delete("", response_model=ApiResponse[InAppNotificationListResponse])
async def clear_notifications(user: CurrentUserDep, service: InboxServiceDep):
    await service.clear(user["user_id"])
    return ok(InAppNotificationListResponse(notifications=[]), message="Notifications cleared")


@notification.get("/stream")
@no_rate_limit
async def stream_notifications(request: Request, user: CurrentUserDep):
    """Server-sent events: one ``notification`` event per InAppNotificationResponse
    as it is created. Missed events are recovered from GET /notifications."""

    async def event_stream():
        async with broker.subscribe(user["user_id"]) as queue:
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"event: notification\ndata: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
