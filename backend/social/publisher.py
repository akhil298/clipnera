"""Publishing one claimed post.

Exactly-once is impossible (no platform accepts an idempotency key), so the
rule is at most once: each provider checkpoints the platform's id for the
upload before the step that makes it public. A post that already has a
checkpoint is never published again -- the platform is asked what happened
to it, and if that cannot be confirmed the post fails with a message telling
the user to check their account rather than risking a duplicate.

Retries: transient errors back off (1m, 5m, 25m, 2h) up to MAX_ATTEMPTS;
quota waits follow the platform's reset time without using up attempts, but
give up once a post is MAX_DELAY late; permanent and auth errors fail at once.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from typing import AsyncIterator

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from clip_generation.model import GeneratedClip
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from feature_flags.registry import SOCIAL_PUBLISHING, social_platform_flag
from feature_flags.service import FeatureFlagService
from social import audit, notify, quota
from social.clip_media import downloaded_clip
from social.credentials import fresh_tokens, mark_needs_reconnect
from social.model import AccountStatus, AuditAction, ConnectedAccount, PostStatus, ScheduledPost
from social.providers import get_provider
from social.providers.base import (
    ErrorKind,
    NotPublished,
    PlatformError,
    PlatformProvider,
    PublishRequest,
    PublishResult,
    TokenSet,
)
from social.tokens import open_text, seal_text

log = get_logger(__name__)

MAX_ATTEMPTS = 5
BACKOFF = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=25), timedelta(hours=2))
MAX_DELAY = timedelta(days=3)
PAUSED_RETRY = timedelta(minutes=10)
HEARTBEAT_SECONDS = 60


def _checkpoint_aad(post_id: str) -> str:
    return f"scheduled_posts:{post_id}:checkpoint"


def backoff_for(attempts: int) -> timedelta:
    return BACKOFF[min(max(attempts, 1), len(BACKOFF)) - 1]


@asynccontextmanager
async def heartbeat(post_id: str) -> AsyncIterator[None]:
    """Keep the claim fresh while publishing, so a long upload is never
    mistaken for a crashed run and picked up by another worker."""

    async def beat() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(ScheduledPost)
                    .where(ScheduledPost.id == post_id, ScheduledPost.status == PostStatus.PUBLISHING)
                    .values(claimed_at=datetime.utcnow())
                )
                await session.commit()

    task = asyncio.create_task(beat())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


class Publisher:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def process(self, post_id: str) -> None:
        session = self._session
        post = await session.get(ScheduledPost, post_id)
        if post is None or post.status != PostStatus.PUBLISHING:
            return
        account = await session.get(ConnectedAccount, post.account_id)
        clip = await session.get(GeneratedClip, post.clip_id)
        flags = await FeatureFlagService(session).effective()
        if not (flags[SOCIAL_PUBLISHING] and flags[social_platform_flag(post.platform.value)]):
            await self._pause(post)
            return
        if account is None or account.status != AccountStatus.ACTIVE or clip is None:
            await self._fail(post, account, PlatformError(
                ErrorKind.PERMANENT, "account_unavailable",
                "The account or clip is no longer available. Reconnect the account and post again.",
            ))
            return
        # Release the connection before the slow part; loaded objects stay usable.
        await session.commit()

        async with get_provider(post.platform) as provider, heartbeat(post.id):
            try:
                tokens = await fresh_tokens(session, account, provider)
                result = await self._run(provider, tokens, post, account, clip)
            except PlatformError as exc:
                await self._handle_error(post, account, exc)
                return
            except Exception as exc:
                log.error(f"Unexpected error publishing post={post.id}: {type(exc).__name__}", exc_info=True)
                await self._handle_error(post, account, PlatformError(
                    ErrorKind.TRANSIENT, "internal_error", "Something went wrong on our side; will retry.",
                ))
                return
        if result is None:
            await self._fail(post, account, PlatformError(
                ErrorKind.PERMANENT, "unconfirmed",
                "We could not confirm whether this was posted. Check your account before posting it again.",
            ))
            return
        await self._succeed(post, account, result)

    async def _run(
        self,
        provider: PlatformProvider,
        tokens: TokenSet,
        post: ScheduledPost,
        account: ConnectedAccount,
        clip: GeneratedClip,
    ) -> PublishResult | None:
        if post.platform_publish_id:
            checkpoint = open_text(post.platform_publish_id, _checkpoint_aad(post.id))
            try:
                return await provider.resolve_checkpoint(tokens, checkpoint, account.handle)
            except NotPublished:
                log.info(f"Post {post.id}: earlier upload never went live; starting over")
                post.platform_publish_id = None
                await self._session.commit()
        return await self._publish(provider, tokens, post, account, clip)

    async def _publish(
        self,
        provider: PlatformProvider,
        tokens: TokenSet,
        post: ScheduledPost,
        account: ConnectedAccount,
        clip: GeneratedClip,
    ) -> PublishResult:
        async with downloaded_clip(clip) as clip_file:
            problems = provider.validate(clip_file, post.caption, post.platform_options or {})
            if problems:
                raise PlatformError(ErrorKind.PERMANENT, "clip_invalid", " ".join(problems))
            await quota.reserve(self._session, post.platform)

            async def save_checkpoint(value: str) -> None:
                post.platform_publish_id = seal_text(value, _checkpoint_aad(post.id))
                await self._session.commit()

            request = PublishRequest(
                caption=post.caption,
                options=post.platform_options or {},
                clip=clip_file,
                account_handle=account.handle,
            )
            return await provider.publish(tokens, request, save_checkpoint)

    # -- outcomes ------------------------------------------------------------------

    async def _succeed(self, post: ScheduledPost, account: ConnectedAccount, result: PublishResult) -> None:
        post.status = PostStatus.PUBLISHED
        post.platform_post_id = result.platform_post_id
        post.post_url = result.post_url
        post.published_at = datetime.utcnow()
        post.error_code = None
        post.error_message = None
        audit.record(
            self._session, AuditAction.POST_PUBLISHED, "system", user_id=post.user_id,
            account_id=account.id, post_id=post.id, platform=post.platform,
            detail={"platform_post_id": result.platform_post_id},
        )
        await self._session.commit()
        log.info(f"Published post={post.id} to {post.platform.value}")

    async def _handle_error(self, post: ScheduledPost, account: ConnectedAccount, exc: PlatformError) -> None:
        log.warning(f"Publish post={post.id} {post.platform.value} failed: {exc.kind.value} {exc.code}")
        now = datetime.utcnow()
        if exc.kind == ErrorKind.AUTH:
            await mark_needs_reconnect(self._session, account, exc.message)
        elif exc.kind == ErrorKind.QUOTA and now - post.scheduled_at < MAX_DELAY:
            # Waiting on a platform reset is not the post's fault; don't spend an attempt.
            post.attempts = max(post.attempts - 1, 0)
            await self._reschedule(post, exc, now + (exc.retry_after or backoff_for(post.attempts + 1)))
            return
        elif exc.kind == ErrorKind.TRANSIENT and post.attempts < MAX_ATTEMPTS and now - post.scheduled_at < MAX_DELAY:
            await self._reschedule(post, exc, now + max(exc.retry_after or timedelta(0), backoff_for(post.attempts)))
            return
        await self._fail(post, account, exc)

    async def _reschedule(self, post: ScheduledPost, exc: PlatformError, at: datetime) -> None:
        post.status = PostStatus.SCHEDULED
        post.next_attempt_at = at
        post.claimed_at = None
        post.error_code = exc.code
        post.error_message = exc.message
        await self._session.commit()

    async def _pause(self, post: ScheduledPost) -> None:
        """Publishing was switched off by an admin: hold the post, spend no attempt."""
        post.attempts = max(post.attempts - 1, 0)
        await self._reschedule(
            post,
            PlatformError(ErrorKind.TRANSIENT, "publishing_paused", "Publishing is paused right now; it will resume automatically."),
            datetime.utcnow() + PAUSED_RETRY,
        )

    async def _fail(self, post: ScheduledPost, account: ConnectedAccount | None, exc: PlatformError) -> None:
        post.status = PostStatus.FAILED
        post.claimed_at = None
        post.error_code = exc.code
        post.error_message = exc.message
        audit.record(
            self._session, AuditAction.POST_FAILED, "system", user_id=post.user_id,
            account_id=post.account_id, post_id=post.id, platform=post.platform,
            detail={"code": exc.code, "kind": exc.kind.value},
        )
        await self._session.commit()
        if account is not None:
            await notify.post_failed(self._session, post, account)
