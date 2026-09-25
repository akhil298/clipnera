"""Connected publishing against a real Postgres database.

Skipped unless TEST_DATABASE_URL points at a disposable database, e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/clipnera_social_test pytest tests/test_social_db.py

Every table in that database is dropped and recreated. Platforms are replaced
by FakeProvider, so no network calls are made.
"""

from __future__ import annotations

import asyncio
import base64
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main
import social.notify
import social.posts
import social.publisher
import social.service
import social.worker
import subscription.service
from auth.dependencies import get_current_user
from auth.model import User, UserRole
from clip.model import ProjectStatus, VideoProject
from clip_generation.model import GeneratedClip
from core import crypto
from core.config import get_settings
from core.database import Base, get_db
from core.exceptions import CustomException
from feature_flags.service import FeatureFlagService
from social.credentials import MAX_REFRESH_FAILURES, fresh_tokens
from social.model import (
    AccountStatus,
    ConnectedAccount,
    OAuthState,
    OAuthToken,
    PostStatus,
    ScheduledPost,
    SocialPlatform,
)
from social.oauth_state import OAuthStateStore
from social.posts import SocialPostService
from social.providers.base import (
    ClipFile,
    ClipLimits,
    ErrorKind,
    NotPublished,
    PlatformError,
    PlatformProvider,
    Profile,
    PublishResult,
    TokenSet,
)
from social.publisher import MAX_ATTEMPTS, Publisher
from social.repository import SocialRepository
from social.schema import CreatePostsRequest, PostTarget
from social.service import SocialAccountService
from social.tokens import TokenStore, seal_text

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
    pytest.mark.asyncio,
]

FAKE = SimpleNamespace()
YT_OPTIONS = {"title": "A clip", "privacy_status": "public", "made_for_kids": False}


def _reset_fake() -> None:
    FAKE.calls = []
    FAKE.profile_id = "channel-1"
    FAKE.publish = lambda: PublishResult("vid-1", "https://youtube.test/vid-1")
    FAKE.resolve = lambda: None
    FAKE.refresh = lambda: TokenSet("access-new", "refresh-new", expires_at=datetime.utcnow() + timedelta(hours=1))


class FakeProvider(PlatformProvider):
    platform = SocialPlatform.YOUTUBE
    label = "YouTube"
    scopes = ("upload",)
    uses_pkce = True
    limits = ClipLimits(max_duration_seconds=180)

    def is_configured(self) -> bool:
        return True

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        return f"https://auth.test/?state={state}&challenge={code_challenge}"

    async def exchange_code(self, code: str, code_verifier: str | None) -> TokenSet:
        FAKE.calls.append(("exchange", code, code_verifier))
        return TokenSet(f"access-{code}", f"refresh-{code}", expires_at=datetime.utcnow() + timedelta(hours=1), scopes="upload")

    async def refresh(self, tokens: TokenSet) -> TokenSet:
        FAKE.calls.append(("refresh", tokens.refresh_token))
        result = FAKE.refresh()
        if isinstance(result, Exception):
            raise result
        return result

    async def revoke(self, tokens: TokenSet) -> None:
        FAKE.calls.append(("revoke", tokens.refresh_token))

    async def fetch_profile(self, tokens: TokenSet) -> Profile:
        return Profile(FAKE.profile_id, "@chan", "Channel", None, 1234)

    async def publish(self, tokens, request, save_checkpoint) -> PublishResult:
        FAKE.calls.append(("publish", tokens.access_token))
        await save_checkpoint("checkpoint-1")
        result = FAKE.publish()
        if isinstance(result, Exception):
            raise result
        return result

    async def resolve_checkpoint(self, tokens, checkpoint, account_handle):
        FAKE.calls.append(("resolve", checkpoint))
        result = FAKE.resolve()
        if isinstance(result, Exception):
            raise result
        return result


def _calls(kind: str) -> list:
    return [c for c in FAKE.calls if c[0] == kind]


@pytest_asyncio.fixture
async def db(monkeypatch, tmp_path: Path):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    settings = get_settings()
    monkeypatch.setattr(settings, "SOCIAL_TOKEN_ENCRYPTION_KEYS", "1:" + base64.b64encode(b"k" * 32).decode())
    monkeypatch.setattr(settings, "SOCIAL_TOKEN_ACTIVE_KEY_VERSION", 1)
    crypto.get_token_cipher.cache_clear()

    _reset_fake()
    for module in (social.service, social.posts, social.publisher, social.worker, social.notify):
        monkeypatch.setattr(module, "get_provider", lambda platform: FakeProvider())
    for module in (social.worker, social.publisher):
        monkeypatch.setattr(module, "AsyncSessionLocal", maker)

    sent = []

    async def _send(session, user_id, subject, body):
        sent.append((user_id, subject))

    monkeypatch.setattr(social.notify, "_send", _send)

    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"v" * 100)

    @asynccontextmanager
    async def _downloaded(clip):
        yield ClipFile(clip_path, 100, 30, 1080, 1920, 30, "h264", "aac", 48000, "mov,mp4")

    monkeypatch.setattr(social.publisher, "downloaded_clip", _downloaded)
    yield SimpleNamespace(maker=maker, sent=sent)
    crypto.get_token_cipher.cache_clear()
    await engine.dispose()


async def _user(maker, role: UserRole = UserRole.USER) -> str:
    async with maker() as session:
        user = User(id=str(uuid4()), email=f"{uuid4().hex[:8]}@test.dev", role=role)
        session.add(user)
        await session.commit()
        return user.id


async def _clip(maker, user_id: str, duration: float = 30) -> str:
    async with maker() as session:
        project = VideoProject(id=str(uuid4()), user_id=user_id, title="p", source_type="upload", status=ProjectStatus.COMPLETED)
        session.add(project)
        await session.flush()
        clip = GeneratedClip(
            id=str(uuid4()), project_id=project.id, user_id=user_id, title="Clip", start_time=0,
            end_time=duration, duration_seconds=duration, s3_key=f"clips/{uuid4()}.mp4", s3_bucket="bucket",
        )
        session.add(clip)
        await session.commit()
        return clip.id


async def _flags(maker, *keys: str, on: bool = True) -> None:
    admin = await _user(maker, UserRole.ADMIN)
    async with maker() as session:
        service = FeatureFlagService(session)
        for key in keys or ("social_publishing", "social_publishing.youtube"):
            await service.set(key, on, admin)


async def _connect(maker, user_id: str, code: str = "code-1") -> str:
    async with maker() as session:
        service = SocialAccountService(session)
        start = await service.start_connect(user_id, SocialPlatform.YOUTUBE)
        state = start.authorize_url.split("state=")[1].split("&")[0]
        account = await service.complete_connect(user_id, SocialPlatform.YOUTUBE, code, state)
        return account.id


def _plan(monkeypatch, plans: dict[str, str]) -> None:
    async def effective(self, user_id):
        return plans.get(user_id, "free")

    monkeypatch.setattr(subscription.service.SubscriptionService, "get_effective_plan", effective)


async def _post(maker, user_id, clip_id, account_id, key=None, scheduled_at=None, options=None):
    async with maker() as session:
        return await SocialPostService(session).create(
            user_id,
            CreatePostsRequest(
                clip_id=clip_id,
                targets=[PostTarget(account_id=account_id, caption="hi", options=options or YT_OPTIONS)],
                scheduled_at=scheduled_at,
                idempotency_key=key or uuid4().hex,
            ),
        )


async def _claim_and_publish(maker) -> None:
    async with maker() as session:
        claimed = await SocialRepository(session).claim_due(datetime.utcnow() + timedelta(seconds=1), 10, timedelta(minutes=15))
    for item in claimed:
        async with maker() as session:
            await Publisher(session).process(item.post_id)


async def _get_post(maker, post_id: str) -> ScheduledPost:
    async with maker() as session:
        return await session.get(ScheduledPost, post_id)


# -- OAuth state ------------------------------------------------------------------


async def test_state_is_single_use_and_bound_to_user_and_platform(db):
    alice, bob = await _user(db.maker), await _user(db.maker)
    async with db.maker() as session:
        store = OAuthStateStore(session)
        state = await store.create(alice, SocialPlatform.YOUTUBE, "verifier-1")
        for user, platform in ((bob, SocialPlatform.YOUTUBE), (alice, SocialPlatform.TIKTOK)):
            with pytest.raises(CustomException) as exc:
                await store.consume(state, user, platform)
            assert exc.value.code == "OAUTH_STATE_INVALID"
        consumed = await store.consume(state, alice, SocialPlatform.YOUTUBE)
        assert consumed.code_verifier == "verifier-1"
        with pytest.raises(CustomException):
            await store.consume(state, alice, SocialPlatform.YOUTUBE)


async def test_state_rejects_missing_and_expired(db):
    alice = await _user(db.maker)
    async with db.maker() as session:
        store = OAuthStateStore(session)
        with pytest.raises(CustomException):
            await store.consume("never-issued", alice, SocialPlatform.YOUTUBE)
        state = await store.create(alice, SocialPlatform.YOUTUBE, None)
        await session.execute(update(OAuthState).values(expires_at=datetime.utcnow() - timedelta(seconds=1)))
        await session.commit()
        with pytest.raises(CustomException):
            await store.consume(state, alice, SocialPlatform.YOUTUBE)


async def test_state_is_stored_hashed_and_verifier_encrypted(db):
    alice = await _user(db.maker)
    async with db.maker() as session:
        state = await OAuthStateStore(session).create(alice, SocialPlatform.YOUTUBE, "verifier-secret")
        row = (await session.execute(select(OAuthState))).scalar_one()
    assert row.state_hash != state and state not in row.state_hash
    assert b"verifier-secret" not in row.code_verifier_ct


async def test_concurrent_replays_of_one_state_succeed_once(db):
    alice = await _user(db.maker)
    async with db.maker() as session:
        state = await OAuthStateStore(session).create(alice, SocialPlatform.YOUTUBE, None)

    async def attempt():
        async with db.maker() as session:
            try:
                await OAuthStateStore(session).consume(state, alice, SocialPlatform.YOUTUBE)
                return True
            except CustomException:
                return False

    assert sorted(await asyncio.gather(*(attempt() for _ in range(5)))) == [False] * 4 + [True]


# -- connecting -------------------------------------------------------------------


async def test_connect_stores_encrypted_tokens_and_profile(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    account_id = await _connect(db.maker, alice)
    assert _calls("exchange")[0][2]  # PKCE verifier reached the exchange
    async with db.maker() as session:
        account = await session.get(ConnectedAccount, account_id)
        row = await session.get(OAuthToken, account_id)
        tokens = await TokenStore(session).load(account_id)
    assert (account.handle, account.follower_count, account.status) == ("@chan", 1234, AccountStatus.ACTIVE)
    assert b"access-code-1" not in row.access_token_ct and b"refresh-code-1" not in row.refresh_token_ct
    assert tokens.access_token == "access-code-1"


async def test_connect_is_refused_while_the_feature_is_off(db):
    alice = await _user(db.maker)
    async with db.maker() as session:
        with pytest.raises(CustomException) as exc:
            await SocialAccountService(session).start_connect(alice, SocialPlatform.YOUTUBE)
    assert exc.value.code == "FEATURE_DISABLED"


async def test_a_platform_account_cannot_be_linked_to_two_users(db):
    await _flags(db.maker)
    alice, bob = await _user(db.maker), await _user(db.maker)
    await _connect(db.maker, alice)
    with pytest.raises(CustomException) as exc:
        await _connect(db.maker, bob, code="code-2")
    assert exc.value.code == "ACCOUNT_LINKED_ELSEWHERE"
    # Bob's fresh grant was revoked rather than left dangling.
    assert ("revoke", "refresh-code-2") in FAKE.calls
    async with db.maker() as session:
        assert await SocialRepository(session).list_accounts(bob) == []


async def test_reconnecting_the_same_account_reactivates_it(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    first = await _connect(db.maker, alice)
    async with db.maker() as session:
        await session.execute(update(ConnectedAccount).values(status=AccountStatus.NEEDS_RECONNECT))
        await session.commit()
    assert await _connect(db.maker, alice, code="code-2") == first
    async with db.maker() as session:
        assert (await session.get(ConnectedAccount, first)).status == AccountStatus.ACTIVE


async def test_free_plan_account_limit(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    await _connect(db.maker, alice)
    FAKE.profile_id = "channel-2"
    with pytest.raises(CustomException) as exc:
        await _connect(db.maker, alice, code="code-2")
    assert exc.value.code == "ACCOUNT_LIMIT_REACHED"


# -- ownership -------------------------------------------------------------------


async def test_users_cannot_touch_each_others_accounts_posts_or_clips(db):
    await _flags(db.maker)
    alice, bob = await _user(db.maker), await _user(db.maker)
    account = await _connect(db.maker, alice)
    clip = await _clip(db.maker, alice)
    post_id = (await _post(db.maker, alice, clip, account)).posts[0].id
    bob_clip = await _clip(db.maker, bob)

    async with db.maker() as session:
        accounts, posts = SocialAccountService(session), SocialPostService(session)
        for call in (
            accounts.disconnect_preview(bob, account),
            accounts.disconnect_for_user(bob, account),
            posts.cancel(bob, post_id),
        ):
            with pytest.raises(CustomException) as exc:
                await call
            assert exc.value.status_code == 404
        assert (await posts.list(bob, None, 50, 0)).posts == []
        assert (await accounts.connections(bob)).accounts == []
    # Posting someone else's clip, or to someone else's account, is refused.
    for user, clip_id in ((bob, clip), (alice, bob_clip)):
        with pytest.raises(CustomException) as exc:
            await _post(db.maker, user, clip_id, account)
        assert exc.value.status_code == 404
    assert (await _get_post(db.maker, post_id)).status == PostStatus.SCHEDULED


# -- creating posts ---------------------------------------------------------------


async def test_retried_submit_creates_posts_once(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    account, clip = await _connect(db.maker, alice), await _clip(db.maker, alice)
    first = await _post(db.maker, alice, clip, account, key="submit-key-1")
    again = await _post(db.maker, alice, clip, account, key="submit-key-1")
    assert [p.id for p in first.posts] == [p.id for p in again.posts]
    async with db.maker() as session:
        assert len((await session.execute(select(ScheduledPost))).scalars().all()) == 1


async def test_free_plan_can_publish_now_but_not_schedule(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    account, clip = await _connect(db.maker, alice), await _clip(db.maker, alice)
    await _post(db.maker, alice, clip, account)
    with pytest.raises(CustomException) as exc:
        await _post(db.maker, alice, clip, account, scheduled_at=datetime.now().astimezone() + timedelta(days=1))
    assert exc.value.code == "PRO_REQUIRED"


async def test_pro_plan_schedules_within_the_window(db, monkeypatch):
    await _flags(db.maker)
    alice = await _user(db.maker)
    _plan(monkeypatch, {alice: "pro"})
    account, clip = await _connect(db.maker, alice), await _clip(db.maker, alice)
    when = datetime.now().astimezone() + timedelta(days=2)
    post = (await _post(db.maker, alice, clip, account, scheduled_at=when)).posts[0]
    assert post.status == "scheduled"
    with pytest.raises(CustomException):
        await _post(db.maker, alice, clip, account, scheduled_at=datetime.now().astimezone() + timedelta(days=31))


async def test_daily_post_limit(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    account, clip = await _connect(db.maker, alice), await _clip(db.maker, alice)
    for _ in range(3):
        await _post(db.maker, alice, clip, account)
    with pytest.raises(CustomException) as exc:
        await _post(db.maker, alice, clip, account)
    assert exc.value.code == "LIMIT_REACHED"


async def test_invalid_options_and_long_clips_fail_early(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    account = await _connect(db.maker, alice)
    long_clip = await _clip(db.maker, alice, duration=400)
    with pytest.raises(CustomException) as exc:
        await _post(db.maker, alice, long_clip, account)
    assert exc.value.code == "VALIDATION_ERROR"


# -- publishing --------------------------------------------------------------------


async def _due_post(db, **kwargs) -> tuple[str, str, str]:
    await _flags(db.maker)
    alice = await _user(db.maker)
    account, clip = await _connect(db.maker, alice), await _clip(db.maker, alice)
    post_id = (await _post(db.maker, alice, clip, account, **kwargs)).posts[0].id
    return alice, account, post_id


async def test_two_workers_never_claim_the_same_post(db):
    alice, account, _ = await _due_post(db)
    clip = await _clip(db.maker, alice)
    async with db.maker() as session:
        for i in range(9):
            session.add(ScheduledPost(
                id=str(uuid4()), user_id=alice, account_id=account, clip_id=clip, publish_group_id="g",
                platform=SocialPlatform.YOUTUBE, caption="", platform_options=YT_OPTIONS,
                scheduled_at=datetime.utcnow(), next_attempt_at=datetime.utcnow(),
                status=PostStatus.SCHEDULED, idempotency_key=f"k{i}",
            ))
        await session.commit()

    async def claim():
        async with db.maker() as session:
            return [c.post_id for c in await SocialRepository(session).claim_due(
                datetime.utcnow() + timedelta(seconds=1), 10, timedelta(minutes=15))]

    results = await asyncio.gather(*(claim() for _ in range(4)))
    claimed = [post_id for result in results for post_id in result]
    assert len(claimed) == len(set(claimed)) == 10


async def test_publish_success(db):
    _, _, post_id = await _due_post(db)
    await _claim_and_publish(db.maker)
    post = await _get_post(db.maker, post_id)
    assert post.status == PostStatus.PUBLISHED
    assert post.post_url == "https://youtube.test/vid-1"
    assert len(_calls("publish")) == 1
    # Already published: another pass does nothing.
    await _claim_and_publish(db.maker)
    assert len(_calls("publish")) == 1


async def test_transient_errors_back_off_then_fail_at_the_cap(db):
    _, _, post_id = await _due_post(db)
    FAKE.publish = lambda: PlatformError(ErrorKind.TRANSIENT, "http_503", "down")
    await _claim_and_publish(db.maker)
    post = await _get_post(db.maker, post_id)
    assert (post.status, post.attempts) == (PostStatus.SCHEDULED, 1)
    assert post.next_attempt_at > datetime.utcnow()

    FAKE.resolve = lambda: NotPublished()
    for _ in range(MAX_ATTEMPTS):
        async with db.maker() as session:
            await session.execute(update(ScheduledPost).values(next_attempt_at=datetime.utcnow() - timedelta(seconds=1)))
            await session.commit()
        await _claim_and_publish(db.maker)
    post = await _get_post(db.maker, post_id)
    assert post.status == PostStatus.FAILED
    assert post.attempts == MAX_ATTEMPTS
    assert db.sent  # the user was told


async def test_permanent_error_fails_at_once(db):
    _, _, post_id = await _due_post(db)
    FAKE.publish = lambda: PlatformError(ErrorKind.PERMANENT, "rejected", "Rejected by policy")
    await _claim_and_publish(db.maker)
    post = await _get_post(db.maker, post_id)
    assert (post.status, post.error_message, post.attempts) == (PostStatus.FAILED, "Rejected by policy", 1)


async def test_auth_error_asks_the_user_to_reconnect(db):
    _, account, post_id = await _due_post(db)
    FAKE.publish = lambda: PlatformError(ErrorKind.AUTH, "revoked", "Reconnect")
    await _claim_and_publish(db.maker)
    async with db.maker() as session:
        assert (await session.get(ConnectedAccount, account)).status == AccountStatus.NEEDS_RECONNECT
    assert (await _get_post(db.maker, post_id)).status == PostStatus.FAILED


async def _with_checkpoint(db, post_id: str) -> None:
    async with db.maker() as session:
        await session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.id == post_id)
            .values(platform_publish_id=seal_text("ck-old", f"scheduled_posts:{post_id}:checkpoint"))
        )
        await session.commit()


async def test_checkpointed_post_is_resolved_never_republished(db):
    _, _, post_id = await _due_post(db)
    await _with_checkpoint(db, post_id)
    FAKE.resolve = lambda: PublishResult("vid-old", "https://youtube.test/vid-old")
    await _claim_and_publish(db.maker)
    post = await _get_post(db.maker, post_id)
    assert (post.status, post.platform_post_id) == (PostStatus.PUBLISHED, "vid-old")
    assert _calls("resolve") == [("resolve", "ck-old")] and _calls("publish") == []


async def test_unconfirmable_outcome_fails_instead_of_risking_a_duplicate(db):
    _, _, post_id = await _due_post(db)
    await _with_checkpoint(db, post_id)
    FAKE.resolve = lambda: None
    await _claim_and_publish(db.maker)
    post = await _get_post(db.maker, post_id)
    assert (post.status, post.error_code) == (PostStatus.FAILED, "unconfirmed")
    assert _calls("publish") == []


async def test_confirmed_unpublished_upload_is_retried_once(db):
    _, _, post_id = await _due_post(db)
    await _with_checkpoint(db, post_id)
    FAKE.resolve = lambda: NotPublished()
    await _claim_and_publish(db.maker)
    assert (await _get_post(db.maker, post_id)).status == PostStatus.PUBLISHED
    assert len(_calls("publish")) == 1


async def test_stuck_publishing_post_is_recovered_after_the_lease(db):
    _, _, post_id = await _due_post(db)
    await _with_checkpoint(db, post_id)
    async with db.maker() as session:
        await session.execute(update(ScheduledPost).values(
            status=PostStatus.PUBLISHING, claimed_at=datetime.utcnow() - timedelta(minutes=5)))
        await session.commit()
        # Within the lease: left alone.
        assert await SocialRepository(session).claim_due(datetime.utcnow(), 10, timedelta(minutes=15)) == []
        await session.execute(update(ScheduledPost).values(claimed_at=datetime.utcnow() - timedelta(minutes=30)))
        await session.commit()
        claimed = await SocialRepository(session).claim_due(datetime.utcnow(), 10, timedelta(minutes=15))
    assert [(c.post_id, c.recovering) for c in claimed] == [(post_id, True)]


async def test_turning_the_feature_off_pauses_without_spending_attempts(db):
    _, _, post_id = await _due_post(db)
    await _flags(db.maker, "social_publishing", on=False)
    await _claim_and_publish(db.maker)
    post = await _get_post(db.maker, post_id)
    assert (post.status, post.attempts, post.error_code) == (PostStatus.SCHEDULED, 0, "publishing_paused")
    assert _calls("publish") == []


# -- tokens ------------------------------------------------------------------------


async def _expire_tokens(db, account_id: str) -> None:
    async with db.maker() as session:
        await session.execute(update(OAuthToken).values(access_expires_at=datetime.utcnow() + timedelta(minutes=1)))
        await session.commit()


async def test_expiring_token_is_refreshed_and_stored(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    account_id = await _connect(db.maker, alice)
    await _expire_tokens(db, account_id)
    async with db.maker() as session:
        account = await session.get(ConnectedAccount, account_id)
        tokens = await fresh_tokens(session, account, FakeProvider())
        stored = await TokenStore(session).load(account_id)
    assert tokens.access_token == stored.access_token == "access-new"


async def test_revoked_grant_moves_account_to_needs_reconnect(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    account_id = await _connect(db.maker, alice)
    await _expire_tokens(db, account_id)
    FAKE.refresh = lambda: PlatformError(ErrorKind.AUTH, "invalid_grant", "revoked")
    async with db.maker() as session:
        account = await session.get(ConnectedAccount, account_id)
        with pytest.raises(PlatformError):
            await fresh_tokens(session, account, FakeProvider())
        assert account.status == AccountStatus.NEEDS_RECONNECT
        assert await session.get(OAuthToken, account_id) is None
    assert db.sent


async def test_repeated_refresh_failures_stop_retrying(db):
    await _flags(db.maker)
    alice = await _user(db.maker)
    account_id = await _connect(db.maker, alice)
    async with db.maker() as session:
        await session.execute(update(OAuthToken).values(access_expires_at=datetime.utcnow() - timedelta(minutes=1)))
        await session.commit()
    FAKE.refresh = lambda: PlatformError(ErrorKind.TRANSIENT, "http_503", "down")
    for _ in range(MAX_REFRESH_FAILURES):
        async with db.maker() as session:
            account = await session.get(ConnectedAccount, account_id)
            with pytest.raises(PlatformError):
                await fresh_tokens(session, account, FakeProvider())
    async with db.maker() as session:
        assert (await session.get(ConnectedAccount, account_id)).status == AccountStatus.NEEDS_RECONNECT


# -- disconnecting -----------------------------------------------------------------


async def test_disconnect_cancels_posts_revokes_and_deletes_tokens(db, monkeypatch):
    await _flags(db.maker)
    alice, bob = await _user(db.maker), await _user(db.maker)
    _plan(monkeypatch, {alice: "pro"})
    account, clip = await _connect(db.maker, alice), await _clip(db.maker, alice)
    post_id = (await _post(
        db.maker, alice, clip, account, scheduled_at=datetime.now().astimezone() + timedelta(days=1)
    )).posts[0].id

    async with db.maker() as session:
        assert (await SocialAccountService(session).disconnect_preview(alice, account)).pending_posts == 1
        assert await SocialAccountService(session).disconnect_for_user(alice, account) == 1
    assert (await _get_post(db.maker, post_id)).status == PostStatus.CANCELLED

    await social.worker.finish_disconnects()
    async with db.maker() as session:
        row = await session.get(ConnectedAccount, account)
        assert row.status == AccountStatus.DISCONNECTED and row.handle is None
        assert await session.get(OAuthToken, account) is None
    assert ("revoke", "refresh-code-1") in FAKE.calls
    # Once fully disconnected, the platform account may be linked by someone else.
    await _connect(db.maker, bob, code="code-2")


async def test_platform_data_deletion_removes_tokens_posts_and_ids(db):
    _, account, post_id = await _due_post(db)
    async with db.maker() as session:
        assert await SocialAccountService(session).platform_removed(SocialPlatform.YOUTUBE, "channel-1", delete_data=True) == 1
    async with db.maker() as session:
        row = await session.get(ConnectedAccount, account)
        assert row.status == AccountStatus.DISCONNECTED
        assert row.platform_user_id.startswith("deleted:")
        assert await session.get(OAuthToken, account) is None
        assert await session.get(ScheduledPost, post_id) is None
    assert _calls("revoke") == []  # the grant was already gone


# -- API guards --------------------------------------------------------------------


@pytest_asyncio.fixture
async def api(db):
    async def _get_db():
        async with db.maker() as session:
            yield session

    def make(user_id: str) -> httpx.AsyncClient:
        main.app.dependency_overrides[get_db] = _get_db
        main.app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")

    yield make
    main.app.dependency_overrides.clear()


async def test_admin_routes_refuse_regular_users(db, api):
    alice = await _user(db.maker)
    client = api(alice)
    for method, path in (
        ("get", "/api/v1/admin/social/overview"),
        ("get", "/api/v1/admin/social/accounts"),
        ("post", "/api/v1/admin/social/accounts/any/disconnect"),
        ("get", "/api/v1/admin/features"),
        ("patch", "/api/v1/admin/features/social_publishing"),
    ):
        response = await client.request(method, path, json={"enabled": True})
        assert response.status_code == 403, path


async def test_admin_can_toggle_the_feature_and_read_stats(db, api):
    admin = await _user(db.maker, UserRole.ADMIN)
    client = api(admin)
    response = await client.patch("/api/v1/admin/features/social_publishing", json={"enabled": True})
    assert response.status_code == 200
    flags = {f["key"]: f for f in response.json()["data"]["flags"]}
    assert flags["social_publishing"]["effective"] is True
    assert flags["social_publishing.youtube"]["effective"] is False
    assert (await client.get("/api/v1/features")).json()["data"]["flags"]["social_publishing"] is True
    overview = (await client.get("/api/v1/admin/social/overview")).json()["data"]
    assert {p["platform"] for p in overview["platforms"]} == {"youtube", "tiktok", "instagram", "x"}


async def test_connections_never_expose_tokens(db, api):
    await _flags(db.maker)
    alice = await _user(db.maker)
    await _connect(db.maker, alice)
    body = (await api(alice).get("/api/v1/social/connections")).text
    assert "access-code-1" not in body and "refresh-code-1" not in body
    assert "@chan" in body


async def test_posting_while_disabled_is_refused(db, api):
    alice = await _user(db.maker)
    clip = await _clip(db.maker, alice)
    response = await api(alice).post("/api/v1/social/posts", json={
        "clip_id": clip, "targets": [{"account_id": "a", "options": {}}], "idempotency_key": "abcdefgh1",
    })
    assert response.status_code == 403
    assert response.json()["error"] == "FEATURE_DISABLED"
