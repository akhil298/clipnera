"""Creating, listing and cancelling posts. Publishing itself happens in the worker."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import CustomException
from feature_flags.registry import SOCIAL_PUBLISHING, social_platform_flag
from feature_flags.service import FeatureFlagService
from social import audit
from social.clip_media import source_of
from social.model import AccountStatus, AuditAction, ConnectedAccount, PostStatus, ScheduledPost
from social.providers import get_provider
from social.providers.base import PlatformError
from social.repository import SocialRepository
from social.schema import CreatePostsRequest, PostListResponse, PostResponse
from social.service import not_found
from subscription.entitlements import Entitlements
from subscription.repository import UsageRepository
from subscription.service import SubscriptionService, pro_required

USAGE_KEY = "social_posts"
# A "publish now" time may lag the server clock slightly; anything older is a mistake.
PAST_TOLERANCE = timedelta(minutes=2)


def idempotency_key(user_id: str, client_key: str, account_id: str) -> str:
    """Scoped to the user and account, so one user's key can never match another's."""
    return hashlib.sha256(f"{user_id}:{client_key}:{account_id}".encode()).hexdigest()


def post_response(post: ScheduledPost, account: ConnectedAccount, clip_title: str) -> PostResponse:
    return PostResponse(
        id=post.id,
        publish_group_id=post.publish_group_id,
        account_id=post.account_id,
        platform=post.platform.value,
        account_handle=account.handle,
        clip_id=post.clip_id,
        clip_title=clip_title,
        caption=post.caption,
        platform_options=post.platform_options or {},
        scheduled_at=post.scheduled_at,
        status=post.status.value,
        post_url=post.post_url,
        error_code=post.error_code,
        error_message=post.error_message,
        attempts=post.attempts,
        published_at=post.published_at,
        created_at=post.created_at,
    )


def invalid(problems: list[str]) -> CustomException:
    return CustomException(
        message=problems[0], code="VALIDATION_ERROR", status_code=422, extra={"problems": problems}
    )


class SocialPostService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SocialRepository(session)
        self._flags = FeatureFlagService(session)
        self._subscriptions = SubscriptionService.for_session(session)

    async def create(self, user_id: str, request: CreatePostsRequest) -> PostListResponse:
        keys = [idempotency_key(user_id, request.idempotency_key, t.account_id) for t in request.targets]
        existing = await self._repo.get_posts_by_keys(keys)
        if existing:
            # A retried submit: return what the first one created, publish nothing new.
            return await self._responses(user_id, existing)

        await self._flags.require(SOCIAL_PUBLISHING)
        ent = await self._subscriptions.get_entitlements(user_id)
        clip = await self._repo.get_clip(request.clip_id, user_id)
        if not clip:
            raise not_found("Clip")
        try:
            source_of(clip)
        except PlatformError as exc:
            raise invalid([exc.message]) from exc
        scheduled_at = self._schedule_time(request.scheduled_at, ent)

        flags = await self._flags.effective()
        accounts: list[ConnectedAccount] = []
        problems: list[str] = []
        for target in request.targets:
            account = await self._repo.get_account(target.account_id, user_id)
            if not account:
                raise not_found()
            provider = get_provider(account.platform)
            if not flags[social_platform_flag(account.platform.value)]:
                problems.append(f"{provider.label} publishing is not available right now.")
            elif account.platform.value not in ent.social_platforms:
                raise pro_required(f"social_{account.platform.value}")
            elif account.status != AccountStatus.ACTIVE:
                problems.append(f"Reconnect your {provider.label} account before posting to it.")
            else:
                problems += provider.precheck(clip.duration_seconds, target.caption, target.options)
            accounts.append(account)
        if problems:
            raise invalid(problems)

        await self._consume_daily_quota(user_id, len(request.targets), ent)
        group_id = str(uuid4())
        posts = [
            ScheduledPost(
                id=str(uuid4()),
                user_id=user_id,
                account_id=account.id,
                clip_id=clip.id,
                publish_group_id=group_id,
                platform=account.platform,
                caption=target.caption,
                platform_options=target.options,
                scheduled_at=scheduled_at,
                next_attempt_at=scheduled_at,
                status=PostStatus.SCHEDULED,
                idempotency_key=key,
            )
            for account, target, key in zip(accounts, request.targets, keys)
        ]
        self._session.add_all(posts)
        for post in posts:
            audit.record(
                self._session, AuditAction.POST_SCHEDULED, "user", actor_user_id=user_id, user_id=user_id,
                account_id=post.account_id, post_id=post.id, platform=post.platform,
                detail={"scheduled_at": scheduled_at.isoformat(), "clip_id": clip.id},
            )
        try:
            await self._session.commit()
        except IntegrityError:
            # The same submit raced in twice; the other one created the posts.
            await self._session.rollback()
            return await self._responses(user_id, await self._repo.get_posts_by_keys(keys))
        return await self._responses(user_id, posts)

    async def list(self, user_id: str, statuses: list[str] | None, limit: int, offset: int) -> PostListResponse:
        statuses = [PostStatus(s) for s in statuses] if statuses else None
        rows = await self._repo.list_posts(user_id, statuses, limit, offset)
        return PostListResponse(posts=[post_response(post, account, clip.title) for post, account, clip in rows])

    async def cancel(self, user_id: str, post_id: str) -> PostResponse:
        post = await self._repo.get_post(post_id, user_id)
        if not post:
            raise not_found("Post")
        if not await self._repo.cancel_post(post_id, user_id):
            raise CustomException(
                message="Only posts that have not started publishing can be cancelled.",
                code="NOT_CANCELLABLE",
                status_code=409,
            )
        audit.record(
            self._session, AuditAction.POST_CANCELLED, "user", actor_user_id=user_id, user_id=user_id,
            account_id=post.account_id, post_id=post.id, platform=post.platform,
        )
        await self._session.commit()
        await self._session.refresh(post)
        return (await self._responses(user_id, [post])).posts[0]

    # -- helpers -----------------------------------------------------------------

    @staticmethod
    def _schedule_time(requested: datetime | None, ent: Entitlements) -> datetime:
        """The publish time as naive UTC, within what the plan allows."""
        now = datetime.utcnow()
        if requested is None:
            return now
        when = requested.astimezone(timezone.utc).replace(tzinfo=None)
        if when < now - PAST_TOLERANCE:
            raise invalid(["Choose a time in the future."])
        if when > now + PAST_TOLERANCE:
            if not ent.social_scheduling:
                raise pro_required("social_scheduling")
            if when > now + timedelta(days=ent.social_max_schedule_days):
                raise invalid([f"Posts can be scheduled up to {ent.social_max_schedule_days} days ahead."])
        return max(when, now)

    async def _consume_daily_quota(self, user_id: str, amount: int, ent: Entitlements) -> None:
        limit = ent.social_posts_per_day
        count = await UsageRepository(self._session).increment(
            user_id, USAGE_KEY, datetime.utcnow().date(), amount, limit
        )
        if count is None:
            raise CustomException(
                message=f"Your plan allows {limit} posts a day. Try again tomorrow or upgrade.",
                code="LIMIT_REACHED",
                status_code=429,
                extra={"feature": USAGE_KEY, "limit": limit},
            )

    async def _responses(self, user_id: str, posts: list[ScheduledPost]) -> PostListResponse:
        responses = []
        for post in posts:
            account = await self._repo.get_account_by_id(post.account_id)
            clip = await self._repo.get_clip(post.clip_id, user_id)
            if account and clip:
                responses.append(post_response(post, account, clip.title))
        return PostListResponse(posts=responses)
