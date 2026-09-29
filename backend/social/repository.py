"""Database access for connected accounts and posts.

Every user-facing read takes the caller's user id and filters on it, so an id
belonging to someone else behaves exactly like one that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from clip_generation.model import GeneratedClip
from social.model import AccountStatus, ConnectedAccount, PostStatus, ScheduledPost, SocialPlatform

LIVE_STATUSES = (AccountStatus.ACTIVE, AccountStatus.NEEDS_RECONNECT, AccountStatus.DISCONNECTING)
PENDING_POST_STATUSES = (PostStatus.SCHEDULED,)


@dataclass(frozen=True)
class ClaimedPost:
    post_id: str
    # True when this is a stuck PUBLISHING post whose earlier run died.
    recovering: bool


class SocialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    # -- accounts --------------------------------------------------------------

    async def list_accounts(self, user_id: str) -> list[ConnectedAccount]:
        result = await self._session.execute(
            select(ConnectedAccount)
            .where(ConnectedAccount.user_id == user_id, ConnectedAccount.status.in_(LIVE_STATUSES))
            .order_by(ConnectedAccount.platform, ConnectedAccount.connected_at)
        )
        return list(result.scalars().all())

    async def get_account(self, account_id: str, user_id: str) -> ConnectedAccount | None:
        result = await self._session.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == account_id,
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.status.in_(LIVE_STATUSES),
            )
        )
        return result.scalar_one_or_none()

    async def get_account_by_id(self, account_id: str) -> ConnectedAccount | None:
        """Any user's account. For the worker, webhooks and admin only."""
        return await self._session.get(ConnectedAccount, account_id)

    async def find_live(self, platform: SocialPlatform, platform_user_id: str) -> ConnectedAccount | None:
        result = await self._session.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.platform == platform,
                ConnectedAccount.platform_user_id == platform_user_id,
                ConnectedAccount.status.in_(LIVE_STATUSES),
            )
        )
        return result.scalar_one_or_none()

    async def count_live_accounts(self, user_id: str) -> int:
        result = await self._session.execute(
            select(func.count(ConnectedAccount.id)).where(
                ConnectedAccount.user_id == user_id, ConnectedAccount.status.in_(LIVE_STATUSES)
            )
        )
        return int(result.scalar_one())

    async def accounts_with_status(self, status: AccountStatus, limit: int) -> list[ConnectedAccount]:
        result = await self._session.execute(
            select(ConnectedAccount).where(ConnectedAccount.status == status).limit(limit)
        )
        return list(result.scalars().all())

    async def accounts_needing_profile_refresh(self, stale_before: datetime, limit: int) -> list[ConnectedAccount]:
        result = await self._session.execute(
            select(ConnectedAccount)
            .where(
                ConnectedAccount.status == AccountStatus.ACTIVE,
                or_(
                    ConnectedAccount.follower_count_updated_at.is_(None),
                    ConnectedAccount.follower_count_updated_at < stale_before,
                ),
            )
            .order_by(ConnectedAccount.follower_count_updated_at.nulls_first())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def accounts_expiring_before(self, before: datetime, limit: int, unwarned: bool) -> list[ConnectedAccount]:
        """Connected (or reconnect-pending) accounts whose lifetime ends before ``before``.
        With ``unwarned``, only those whose user has not been told yet."""
        query = select(ConnectedAccount).where(
            ConnectedAccount.status.in_((AccountStatus.ACTIVE, AccountStatus.NEEDS_RECONNECT)),
            ConnectedAccount.expires_at.is_not(None),
            ConnectedAccount.expires_at < before,
        )
        if unwarned:
            query = query.where(ConnectedAccount.expiry_warned_at.is_(None))
        result = await self._session.execute(query.order_by(ConnectedAccount.expires_at).limit(limit))
        return list(result.scalars().all())

    async def user_account_ids(self, user_id: str) -> list[str]:
        result = await self._session.execute(
            select(ConnectedAccount.id).where(
                ConnectedAccount.user_id == user_id, ConnectedAccount.status.in_(LIVE_STATUSES)
            )
        )
        return list(result.scalars().all())

    # -- clips -----------------------------------------------------------------

    async def get_clip(self, clip_id: str, user_id: str) -> GeneratedClip | None:
        result = await self._session.execute(
            select(GeneratedClip).where(GeneratedClip.id == clip_id, GeneratedClip.user_id == user_id)
        )
        return result.scalar_one_or_none()

    # -- posts -----------------------------------------------------------------

    async def get_post(self, post_id: str, user_id: str) -> ScheduledPost | None:
        result = await self._session.execute(
            select(ScheduledPost).where(ScheduledPost.id == post_id, ScheduledPost.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_posts_by_keys(self, keys: list[str]) -> list[ScheduledPost]:
        result = await self._session.execute(select(ScheduledPost).where(ScheduledPost.idempotency_key.in_(keys)))
        return list(result.scalars().all())

    async def list_posts(
        self, user_id: str, statuses: list[PostStatus] | None, limit: int, offset: int
    ) -> list[tuple[ScheduledPost, ConnectedAccount, GeneratedClip]]:
        stmt = (
            select(ScheduledPost, ConnectedAccount, GeneratedClip)
            .join(ConnectedAccount, ConnectedAccount.id == ScheduledPost.account_id)
            .join(GeneratedClip, GeneratedClip.id == ScheduledPost.clip_id)
            .where(ScheduledPost.user_id == user_id)
        )
        if statuses:
            stmt = stmt.where(ScheduledPost.status.in_(statuses))
        stmt = stmt.order_by(ScheduledPost.scheduled_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [tuple(row) for row in result.all()]

    async def count_pending_posts(self, account_id: str) -> int:
        result = await self._session.execute(
            select(func.count(ScheduledPost.id)).where(
                ScheduledPost.account_id == account_id, ScheduledPost.status.in_(PENDING_POST_STATUSES)
            )
        )
        return int(result.scalar_one())

    async def cancel_pending_posts(self, account_id: str, reason: str) -> list[str]:
        """Cancel every not-yet-started post for an account. Does not commit."""
        result = await self._session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.account_id == account_id, ScheduledPost.status.in_(PENDING_POST_STATUSES))
            .values(status=PostStatus.CANCELLED, error_code="account_disconnected", error_message=reason)
            .returning(ScheduledPost.id)
        )
        return list(result.scalars().all())

    async def cancel_post(self, post_id: str, user_id: str) -> bool:
        """Cancel one post if it has not started publishing. Commits."""
        result = await self._session.execute(
            update(ScheduledPost)
            .where(
                ScheduledPost.id == post_id,
                ScheduledPost.user_id == user_id,
                ScheduledPost.status == PostStatus.SCHEDULED,
            )
            .values(status=PostStatus.CANCELLED, error_code="cancelled", error_message="Cancelled by you.")
            .returning(ScheduledPost.id)
        )
        cancelled = result.first() is not None
        await self._session.commit()
        return cancelled

    async def claim_due(self, now: datetime, limit: int, lease: timedelta) -> list[ClaimedPost]:
        """Take due posts (and stuck ones whose lease ran out) for this worker. Commits.

        FOR UPDATE SKIP LOCKED means concurrent workers never pick the same row,
        and the status change is committed before any platform is called.
        """
        stale = now - lease
        result = await self._session.execute(
            select(ScheduledPost.id, ScheduledPost.status)
            .where(
                or_(
                    and_(ScheduledPost.status == PostStatus.SCHEDULED, ScheduledPost.next_attempt_at <= now),
                    and_(ScheduledPost.status == PostStatus.PUBLISHING, ScheduledPost.claimed_at < stale),
                )
            )
            .order_by(ScheduledPost.next_attempt_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = result.all()
        if not rows:
            await self._session.commit()
            return []
        ids = [post_id for post_id, _ in rows]
        await self._session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.id.in_(ids))
            .values(
                attempts=case(
                    (ScheduledPost.status == PostStatus.SCHEDULED, ScheduledPost.attempts + 1),
                    else_=ScheduledPost.attempts,
                ),
                status=PostStatus.PUBLISHING,
                claimed_at=now,
            )
        )
        await self._session.commit()
        return [ClaimedPost(post_id, status == PostStatus.PUBLISHING) for post_id, status in rows]

    # -- admin -------------------------------------------------------------------

    async def account_counts(self) -> list[tuple[SocialPlatform, AccountStatus, int]]:
        result = await self._session.execute(
            select(ConnectedAccount.platform, ConnectedAccount.status, func.count(ConnectedAccount.id)).group_by(
                ConnectedAccount.platform, ConnectedAccount.status
            )
        )
        return [tuple(row) for row in result.all()]

    async def post_counts(self, since: datetime) -> list[tuple[SocialPlatform, PostStatus, int]]:
        result = await self._session.execute(
            select(ScheduledPost.platform, ScheduledPost.status, func.count(ScheduledPost.id))
            .where(ScheduledPost.updated_at >= since)
            .group_by(ScheduledPost.platform, ScheduledPost.status)
        )
        return [tuple(row) for row in result.all()]

    async def recent_failures(self, limit: int) -> list[tuple[ScheduledPost, ConnectedAccount, User]]:
        result = await self._session.execute(
            select(ScheduledPost, ConnectedAccount, User)
            .join(ConnectedAccount, ConnectedAccount.id == ScheduledPost.account_id)
            .join(User, User.id == ScheduledPost.user_id)
            .where(ScheduledPost.status == PostStatus.FAILED)
            .order_by(ScheduledPost.updated_at.desc())
            .limit(limit)
        )
        return [tuple(row) for row in result.all()]

    async def admin_accounts(
        self, query: str | None, limit: int, offset: int
    ) -> list[tuple[ConnectedAccount, User]]:
        stmt = (
            select(ConnectedAccount, User)
            .join(User, User.id == ConnectedAccount.user_id)
            .where(ConnectedAccount.status.in_(LIVE_STATUSES))
        )
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(or_(User.email.ilike(pattern), ConnectedAccount.handle.ilike(pattern)))
        stmt = stmt.order_by(ConnectedAccount.connected_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [tuple(row) for row in result.all()]
