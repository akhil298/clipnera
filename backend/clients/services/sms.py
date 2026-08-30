from __future__ import annotations

from typing import Any

from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from core.config import get_settings
from core.exceptions import CustomException

settings = get_settings()


class SMSClient:
    """SMS client via Twilio."""

    def __init__(self) -> None:
        self._client = TwilioClient(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )
        self._from_number = settings.TWILIO_PHONE_NUMBER

    def send(self, to: str, message: str) -> str:
        try:
            msg = self._client.messages.create(
                body=message,
                from_=self._from_number,
                to=to,
            )
            return msg.sid
        except TwilioRestException as e:
            raise CustomException(
                message=f"Failed to send SMS: {e.msg}",
                code="SMS_SEND_FAILED",
                status_code=502,
            ) from e
