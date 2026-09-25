from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from social.model import AuditAction, PublishAuditLog, SocialPlatform

ActorType = Literal["user", "admin", "system", "webhook"]


def record(
    session: AsyncSession,
    action: AuditAction,
    actor_type: ActorType,
    *,
    actor_user_id: str | None = None,
    user_id: str | None = None,
    account_id: str | None = None,
    post_id: str | None = None,
    platform: SocialPlatform | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Add an audit entry to the session; it commits with the change it describes.

    ``detail`` is for ids, counts and error codes. Never put token values,
    authorization codes or other secrets in it.
    """
    session.add(
        PublishAuditLog(
            action=action,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            user_id=user_id,
            account_id=account_id,
            post_id=post_id,
            platform=platform,
            detail=detail,
        )
    )
