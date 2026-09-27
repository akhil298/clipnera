"""Signed one-click links that turn off a user's account emails.

The token names the user and is signed with SECRET_KEY, so the link works
without signing in and cannot be forged for someone else. It does not expire:
an unsubscribe link in an old email must keep working.
"""

from __future__ import annotations

from itsdangerous import BadSignature, URLSafeSerializer

from core.config import get_settings

_SALT = "email-unsubscribe"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().SECRET_KEY, salt=_SALT)


def unsubscribe_token(user_id: str) -> str:
    return _serializer().dumps(user_id)


def user_id_from_token(token: str) -> str | None:
    try:
        user_id = _serializer().loads(token)
    except BadSignature:
        return None
    return user_id if isinstance(user_id, str) else None


def unsubscribe_url(user_id: str) -> str:
    return f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/unsubscribe?token={unsubscribe_token(user_id)}"
