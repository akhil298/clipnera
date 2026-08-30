from __future__ import annotations

import asyncio

from auth.model import AuthProvider, UserAccount
from core.security import create_access_token


async def send_password_reset_email(user_id: str, email: str) -> None:
    """Generate reset token and send email (simulated)."""
    token = create_access_token(
        subject=user_id,
        expires_delta=__import__("datetime").timedelta(minutes=30),
    )
    # TODO: integrate with email service (SES, SendGrid, etc.)
    await asyncio.sleep(0)  # yield control, non-blocking
    print(f"[Password Reset] Token for {email}: {token}")
