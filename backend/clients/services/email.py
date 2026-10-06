from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from core.config import get_settings
from core.exceptions import CustomException

settings = get_settings()


class EmailClient:
    """Async-capable email client via AWS SES."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "ses",
            endpoint_url=settings.LOCALSTACK_ENDPOINT or None,
            region_name=settings.SES_REGION or settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )

    def send(self, to: str, subject: str, body: str, sender: str | None = None) -> str:
        sender = sender or settings.EMAIL_SENDER
        try:
            response = self._client.send_email(
                Source=sender,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Html": {"Data": body, "Charset": "UTF-8"}},
                },
            )
            return response["MessageId"]
        except Exception as e:
            raise CustomException(
                message=f"Failed to send email: {str(e)}",
                code="EMAIL_SEND_FAILED",
                status_code=502,
            ) from e
