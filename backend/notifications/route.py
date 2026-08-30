from fastapi import APIRouter

from notifications.dependencies import NotificationServiceDep
from notifications.schema import SendEmailRequest, SendSMSRequest, NotificationResponse

notification = APIRouter(prefix="/notifications", tags=["notifications"])


@notification.post("/email", response_model=NotificationResponse)
async def send_email(data: SendEmailRequest, service: NotificationServiceDep):
    message_id = service.send_email(to=data.to, subject=data.subject, body=data.body, sender=data.sender)
    return NotificationResponse(id=message_id, channel="email")


@notification.post("/sms", response_model=NotificationResponse)
async def send_sms(data: SendSMSRequest, service: NotificationServiceDep):
    message_id = service.send_sms(to=data.to, message=data.message)
    return NotificationResponse(id=message_id, channel="sms")
