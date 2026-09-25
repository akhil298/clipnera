"""Emails about connected accounts and posts. Best effort: a failed email never
blocks the state change it reports."""

from __future__ import annotations

import asyncio
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from clients.services.email import EmailClient
from core.config import get_settings
from core.logging_config import get_logger
from social.model import ConnectedAccount, ScheduledPost
from social.providers import get_provider

log = get_logger(__name__)


async def _send(session: AsyncSession, user_id: str, subject: str, body: str) -> None:
    user = await session.get(User, user_id)
    if not user or not user.email:
        return
    try:
        await asyncio.to_thread(EmailClient().send, user.email, subject, body)
    except Exception as exc:
        log.warning(f"Could not send social notification to user={user_id}: {type(exc).__name__}")


def _settings_link() -> str:
    return f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/dashboard/settings"


async def account_needs_reconnect(session: AsyncSession, account: ConnectedAccount) -> None:
    label = get_provider(account.platform).label
    name = escape(account.handle or account.display_name or label)
    await _send(
        session,
        account.user_id,
        f"Clipnera: reconnect your {label} account",
        f"<p>Clipnera can no longer post to {label} as <b>{name}</b>: access expired or was removed.</p>"
        f"<p>Scheduled posts for this account will fail until you reconnect it in "
        f'<a href="{_settings_link()}">Settings → Social accounts</a>.</p>',
    )


async def post_failed(session: AsyncSession, post: ScheduledPost, account: ConnectedAccount) -> None:
    label = get_provider(post.platform).label
    await _send(
        session,
        post.user_id,
        f"Clipnera: a {label} post failed",
        f"<p>Your post to {label} ({escape(account.handle or '')}) could not be published.</p>"
        f"<p>Reason: {escape(post.error_message or 'Unknown error')}</p>"
        f'<p>See details in the <a href="{get_settings().PUBLIC_APP_URL.rstrip("/")}/dashboard/scheduler">scheduler</a>.</p>',
    )
