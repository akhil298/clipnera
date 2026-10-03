"""The flag engine, admin API and legacy routes against a real Postgres database.

Skipped unless TEST_DATABASE_URL points at a disposable database, e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/flags_test pytest tests/test_flags_db.py

Every table in that database is dropped and recreated.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import Request
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main
from auth.dependencies import get_current_user
from auth.model import User, UserRole
from core.database import Base, get_db
from core.security import create_access_token
from feature_flags.dependencies import bearer_user_id
from feature_flags.engine import FlagEngine, flags
from feature_flags.model import ALL_PERMISSIONS, FLAGS_VIEW, AdminPermission, FeatureFlag, FlagAuditLog
from feature_flags.registry import (
    AGENT_EDITOR,
    BROLL_REELS,
    BROLL_STUDIO,
    FLAGS,
    LEGACY_KEYS,
    NEW_UI_ADMIN,
    NEW_UI_SHELL,
    REEL_EDITOR,
    REEL_EDITOR_OPUS,
)
from feature_flags.repository import FlagRepository
from feature_flags.service import FeatureFlagService

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
    pytest.mark.asyncio,
]
REASON = "Testing the flag console"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with maker() as session:
            yield session

    main.app.dependency_overrides[get_db] = _get_db
    main.app.dependency_overrides[get_current_user] = _current_user
    assert not flags.started
    yield maker, engine
    main.app.dependency_overrides.clear()
    await engine.dispose()


def _current_user(request: Request) -> dict:
    """The real header check, minus the activity write."""
    return {"user_id": bearer_user_id(request)}


async def _user(maker, role: UserRole = UserRole.USER, permissions=()) -> User:
    async with maker() as session:
        user = User(id=str(uuid4()), email=f"{uuid4().hex[:8]}@test.dev", role=role)
        session.add(user)
        await session.flush()
        session.add_all(AdminPermission(user_id=user.id, permission=p) for p in permissions)
        await session.commit()
        return user


def _client(user: User | None) -> httpx.AsyncClient:
    headers = {}
    if user is not None:
        headers["Authorization"] = f"Bearer {create_access_token(user.id)}"
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test", headers=headers)


async def _admin(maker, permissions=ALL_PERMISSIONS) -> tuple[User, httpx.AsyncClient]:
    admin = await _user(maker, UserRole.ADMIN, permissions)
    return admin, _client(admin)


async def _audit(maker) -> list[FlagAuditLog]:
    async with maker() as session:
        return list((await session.scalars(select(FlagAuditLog).order_by(FlagAuditLog.id))).all())


async def _features(user: User) -> dict[str, bool]:
    async with _client(user) as client:
        return (await client.get("/api/v1/features")).json()["data"]["flags"]


async def _update(client, key, version, **body):
    payload = {"expected_version": version, "enabled": True, "rules": [], "rollout_bps": 10000, "reason": REASON}
    return await client.patch(f"/api/v1/admin/flags/{key}", json={**payload, **body})


# -- legacy contract -----------------------------------------------------------------------


async def test_legacy_routes_keep_their_shapes(db):
    maker, _ = db
    admin, client = await _admin(maker)
    async with client:
        listed = (await client.get("/api/v1/admin/features")).json()
        patched = await client.patch("/api/v1/admin/features/social_publishing", json={"enabled": True})
    assert set(listed) == {"data", "message", "error"}
    assert {item["key"] for item in listed["data"]["flags"]} == LEGACY_KEYS
    assert all(set(item) == {"key", "label", "description", "parent", "enabled", "effective", "updated_at"}
               for item in listed["data"]["flags"])
    assert patched.status_code == 200 and patched.json()["message"] == "Feature updated"
    by_key = {item["key"]: item for item in patched.json()["data"]["flags"]}
    assert by_key["social_publishing"] == {**by_key["social_publishing"], "enabled": True, "effective": True}

    features = await _features(admin)
    assert set(features) == {key for key in FLAGS if key in LEGACY_KEYS or FLAGS[key].client}
    assert features["social_publishing"] is True and features[NEW_UI_SHELL] is False

    [entry] = await _audit(maker)
    assert (entry.action, entry.target_key, entry.reason, entry.actor_email) == (
        "legacy.switch", "social_publishing", "Legacy switch (no reason)", admin.email)
    assert entry.before is None and entry.after["enabled"] is True


async def test_legacy_patch_refuses_new_flags(db):
    maker, _ = db
    _, client = await _admin(maker)
    async with client:
        response = await client.patch(f"/api/v1/admin/features/{NEW_UI_SHELL}", json={"enabled": True})
    assert response.status_code == 404 and response.json()["error"] == "NOT_FOUND"


async def test_rows_from_before_the_migration_keep_their_state(db):
    """Plain switches (only key/enabled set; server defaults for the rest) stay on for everyone."""
    maker, _ = db
    async with maker() as session:
        await session.execute(text(
            "INSERT INTO feature_flags (key, enabled, updated_at) VALUES "
            "('broll_studio', true, now()), ('broll_studio.reels', true, now()), ('video_upload', false, now())"
        ))
        await session.commit()
        row = await session.get(FeatureFlag, BROLL_STUDIO)
        assert (row.rollout_bps, row.rules, row.killed, row.version) == (10000, [], False, 1)
    features = await _features(await _user(maker))
    assert (features[BROLL_STUDIO], features[BROLL_REELS], features["video_upload"]) == (True, True, False)


async def test_grandchild_bug_is_kept_until_the_switch_is_flipped(db):
    maker, _ = db
    admin, client = await _admin(maker)
    async with maker() as session:
        service = FeatureFlagService(session)
        for key in (BROLL_REELS, REEL_EDITOR, REEL_EDITOR_OPUS):
            await service.set(key, True, admin.id)
    async with maker() as session:
        assert await FeatureFlagService(session).is_enabled(REEL_EDITOR_OPUS)
    async with client:
        response = await client.patch("/api/v1/admin/config/flags.legacy_parent_semantics", json={
            "expected_version": 0, "default_value": False, "rules": [], "reason": REASON})
    assert response.status_code == 200, response.text
    async with maker() as session:
        effective = await FeatureFlagService(session).effective()
    assert not effective[REEL_EDITOR] and not effective[REEL_EDITOR_OPUS]


# -- admin flags API -----------------------------------------------------------------------


async def test_update_flag_with_optimistic_concurrency_and_audit(db):
    maker, _ = db
    _, client = await _admin(maker)
    async with client:
        first = await _update(client, NEW_UI_SHELL, 0, rollout_bps=2500)
        stale = await _update(client, NEW_UI_SHELL, 0, rollout_bps=5000)
        listed = (await client.get("/api/v1/admin/flags")).json()["data"]
    assert first.status_code == 200 and first.json()["data"]["version"] == 1
    assert first.json()["data"]["rollout_bps"] == 2500
    assert stale.status_code == 409 and stale.json()["error"] == "FLAG_VERSION_CONFLICT"
    assert stale.json()["version"] == 1
    assert len(listed["flags"]) == len(FLAGS) and listed["snapshot_version"] == 2
    entries = await _audit(maker)
    assert [e.action for e in entries] == ["flag.update"] and entries[0].after["rollout_bps"] == 2500


async def test_rules_are_validated(db):
    maker, _ = db
    _, client = await _admin(maker)
    rule = {"id": "r_x", "when": {"segments": ["nobody"]}, "serve": True}
    async with client:
        unknown_segment = await _update(client, NEW_UI_SHELL, 0, rules=[rule])
        unknown_plan = await _update(client, NEW_UI_SHELL, 0, rules=[{**rule, "when": {"plans": ["gold"]}}])
        short_reason = await _update(client, NEW_UI_SHELL, 0, reason="short")
    assert unknown_segment.status_code == 422 and unknown_segment.json()["field"] == "rules.r_x.when.segments"
    assert unknown_plan.status_code == 422
    assert short_reason.status_code == 422
    assert await _audit(maker) == []


async def test_staff_rule_and_segment_membership(db):
    maker, _ = db
    admin, client = await _admin(maker)
    member, outsider = await _user(maker), await _user(maker)
    staff_rule = {"id": "r_staff", "when": {"segments": ["staff"]}, "serve": True}
    async with client:
        await _update(client, NEW_UI_ADMIN, 0, rules=[staff_rule], rollout_bps=0)
        segments = (await client.get("/api/v1/admin/segments")).json()["data"]["segments"]
        staff = next(s for s in segments if s["key"] == "staff")
        added = await client.patch("/api/v1/admin/segments/staff", json={
            "expected_version": staff["version"], "add_users": [member.email], "reason": REASON})
    assert added.status_code == 200
    assert (await _features(admin))[NEW_UI_ADMIN] is True
    assert (await _features(member))[NEW_UI_ADMIN] is True
    assert (await _features(outsider))[NEW_UI_ADMIN] is False


async def test_kill_cascades_and_restore_returns_to_the_same_targeting(db):
    maker, _ = db
    admin, client = await _admin(maker)
    async with client:
        for key in (BROLL_STUDIO, BROLL_REELS, REEL_EDITOR):
            await client.patch(f"/api/v1/admin/features/{key}", json={"enabled": True})
        unconfirmed = await client.post(f"/api/v1/admin/flags/{BROLL_STUDIO}/kill",
                                        json={"reason": REASON, "confirm_key": BROLL_REELS})
        killed = await client.post(f"/api/v1/admin/flags/{BROLL_STUDIO}/kill",
                                   json={"reason": REASON, "confirm_key": BROLL_STUDIO})
        killed_features = await _features(admin)
        detail = (await client.get(f"/api/v1/admin/flags/{REEL_EDITOR}")).json()["data"]
        restored = await client.post(f"/api/v1/admin/flags/{BROLL_STUDIO}/unkill", json={"reason": REASON})
    assert unconfirmed.status_code == 422
    assert killed.json()["data"]["killed"] is True and killed.json()["data"]["killed_reason"] == REASON
    assert killed.json()["data"]["killed_by_email"] == admin.email
    assert not any(killed_features[key] for key in (BROLL_STUDIO, BROLL_REELS, REEL_EDITOR))
    assert detail["blocked_by"] == BROLL_STUDIO and detail["enabled"] is True
    assert restored.json()["data"]["killed"] is False
    restored_features = await _features(admin)
    assert all(restored_features[key] for key in (BROLL_STUDIO, BROLL_REELS, REEL_EDITOR))
    assert [e.action for e in await _audit(maker)][-2:] == ["flag.kill", "flag.unkill"]


async def test_overrides_by_email_and_delete_with_reason(db):
    maker, _ = db
    _, client = await _admin(maker)
    alice = await _user(maker)
    async with client:
        await _update(client, NEW_UI_SHELL, 0, rollout_bps=0)
        not_bool = await client.put(f"/api/v1/admin/flags/{NEW_UI_SHELL}/overrides", json={
            "subject_type": "user", "subject": alice.email, "value": 1, "reason": REASON})
        saved = await client.put(f"/api/v1/admin/flags/{NEW_UI_SHELL}/overrides", json={
            "subject_type": "user", "subject": alice.email.upper(), "value": True, "reason": REASON})
        evaluated = await client.post(f"/api/v1/admin/flags/{NEW_UI_SHELL}/evaluate", json={"user": alice.email})
        on = await _features(alice)
        removed = await client.delete(
            f"/api/v1/admin/flags/{NEW_UI_SHELL}/overrides/user/{alice.id}", params={"reason": REASON})
    assert not_bool.status_code == 422
    [entry] = saved.json()["data"]["overrides"]
    assert (entry["subject_id"], entry["subject_label"], entry["value"]) == (alice.id, alice.email, True)
    assert evaluated.json()["data"]["reason"] == "USER_OVERRIDE"
    assert on[NEW_UI_SHELL] is True
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["overrides"] == [] and (await _features(alice))[NEW_UI_SHELL] is False
    actions = [(e.action, e.subject_type, e.subject_id) for e in await _audit(maker)]
    assert actions[-2:] == [("override.set", "user", alice.id), ("override.delete", "user", alice.id)]


# -- remote config ------------------------------------------------------------------------


async def test_config_is_validated_and_served(db):
    maker, _ = db
    _, client = await _admin(maker)
    alice = await _user(maker)
    base = {"expected_version": 0, "rules": [], "reason": REASON}
    async with client:
        out_of_range = await client.patch("/api/v1/admin/config/agent.approval_credit_threshold",
                                          json={**base, "default_value": 20000})
        wrong_type = await client.patch("/api/v1/admin/config/agent.approval_credit_threshold",
                                        json={**base, "default_value": True})
        global_rule = await client.patch("/api/v1/admin/config/rate_limit.default_per_minute", json={
            **base, "rules": [{"id": "r_a", "when": {}, "serve": 100}]})
        saved = await client.patch("/api/v1/admin/config/agent.approval_credit_threshold", json={
            **base, "default_value": 90, "rules": [{"id": "r_pro", "when": {"plans": ["pro"]}, "serve": 300}]})
    for response in (out_of_range, wrong_type, global_rule):
        assert response.status_code == 422 and response.json()["error"] == "CONFIG_INVALID"
    detail = saved.json()["data"]
    assert detail["by_plan"]["pro"] == 300 and detail["by_plan"]["free"] == 90
    assert detail["by_plan"]["pro_plus"] == 90
    async with _client(alice) as alice_client:
        bootstrap = (await alice_client.get("/api/v1/flags/bootstrap")).json()["data"]
    assert bootstrap["subject"] == "user" and bootstrap["config"]["agent.approval_credit_threshold"] == 90
    assert [e.action for e in await _audit(maker)] == ["config.update"]


# -- bootstrap ------------------------------------------------------------------------------


async def test_bootstrap_signed_out_sets_the_anon_cookie(db):
    async with _client(None) as client:
        response = await client.get("/api/v1/flags/bootstrap")
        again = await client.get("/api/v1/flags/bootstrap", cookies={"cn_anon": "abc"})
        bad_token = await client.get("/api/v1/flags/bootstrap", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    assert "cn_anon=" in response.headers["set-cookie"] and "samesite=lax" in response.headers["set-cookie"].lower()
    assert response.json()["data"]["subject"] == "anonymous" and response.json()["data"]["flags"] == {}
    assert "set-cookie" not in again.headers
    assert bad_token.status_code == 401


# -- permissions --------------------------------------------------------------------------


async def test_permissions(db):
    maker, _ = db
    viewer, viewer_client = await _admin(maker, permissions=(FLAGS_VIEW,))
    _, ungranted_client = await _admin(maker, permissions=())
    regular = _client(await _user(maker))
    async with viewer_client, ungranted_client, regular:
        assert (await viewer_client.get("/api/v1/admin/flags")).status_code == 200
        kill = await viewer_client.post(f"/api/v1/admin/flags/{AGENT_EDITOR}/kill",
                                        json={"reason": REASON, "confirm_key": AGENT_EDITOR})
        assert kill.status_code == 403 and kill.json() == {
            "permission": "flags.kill", "error": "FORBIDDEN", "message": "You do not have permission to do this."}
        # An admin with grants is held to them on the legacy routes too.
        legacy = await viewer_client.patch("/api/v1/admin/features/video_upload", json={"enabled": True})
        assert legacy.status_code == 403
        # An admin with no grants at all keeps the legacy page, but not the new API.
        assert (await ungranted_client.get("/api/v1/admin/features")).status_code == 200
        assert (await ungranted_client.get("/api/v1/admin/flags")).status_code == 403
        assert (await regular.get("/api/v1/admin/flags")).status_code == 403


# -- audit log ------------------------------------------------------------------------------


async def test_audit_log_is_append_only(db):
    maker, _ = db
    async with maker() as session:
        session.add(FlagAuditLog(action="flag.update", target_kind="flag", target_key="x", reason=REASON))
        await session.commit()
    for statement in (update(FlagAuditLog).values(reason="rewritten history"), delete(FlagAuditLog)):
        async with maker() as session:
            with pytest.raises(DBAPIError, match="append-only"):
                await session.execute(statement)
    assert [e.reason for e in await _audit(maker)] == [REASON]


async def test_a_failed_write_leaves_no_audit_row_and_no_change(db, monkeypatch):
    maker, _ = db
    _, client = await _admin(maker)

    async def broken(self):
        raise RuntimeError("database went away")

    monkeypatch.setattr(FlagRepository, "bump_version", broken)
    async with client:
        with pytest.raises(RuntimeError):
            await _update(client, NEW_UI_SHELL, 0)
    async with maker() as session:
        assert await session.get(FeatureFlag, NEW_UI_SHELL) is None
    assert await _audit(maker) == []


async def test_audit_pages_with_a_cursor(db, monkeypatch):
    maker, _ = db
    _, client = await _admin(maker)
    monkeypatch.setattr("feature_flags.admin_service.AUDIT_PAGE_SIZE", 2)
    async with client:
        for version in range(3):
            await _update(client, NEW_UI_SHELL, version, rollout_bps=1000 * (version + 1))
        first = (await client.get(f"/api/v1/admin/flags/{NEW_UI_SHELL}/history")).json()["data"]
        second = (await client.get("/api/v1/admin/flags/audit", params={"cursor": first["next_cursor"]})).json()
    assert [e["after"]["rollout_bps"] for e in first["entries"]] == [3000, 2000]
    assert [e["after"]["rollout_bps"] for e in second["data"]["entries"]] == [1000]
    assert second["data"]["next_cursor"] is None


# -- engine: snapshot, NOTIFY and poll ------------------------------------------------------


async def _write_elsewhere(maker, key: str) -> int:
    """A write by another process: row, version bump and NOTIFY, without touching this engine."""
    async with maker() as session:
        await session.execute(insert(FeatureFlag).values(key=key, enabled=True))
        version = await FlagRepository(session).bump_version()
        await session.commit()
    return version


async def _wait_for(engine: FlagEngine, version: int) -> None:
    for _ in range(100):
        if engine.snapshot.version == version:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"snapshot stayed at {engine.snapshot.version}, wanted {version}")


async def test_notify_swaps_the_snapshot_and_checks_need_no_queries(db):
    maker, sa_engine = db
    engine = FlagEngine()
    await engine.start(maker, sa_engine, poll_seconds=3600)
    try:
        assert engine.listening and not engine.is_enabled(AGENT_EDITOR)
        version = await _write_elsewhere(maker, AGENT_EDITOR)
        await _wait_for(engine, version)
        queries = []
        from sqlalchemy import event

        listener = lambda *args: queries.append(args)  # noqa: E731
        event.listen(sa_engine.sync_engine, "before_cursor_execute", listener)
        try:
            assert all(engine.is_enabled(AGENT_EDITOR) for _ in range(100))
        finally:
            event.remove(sa_engine.sync_engine, "before_cursor_execute", listener)
        assert queries == []
    finally:
        await engine.stop()


async def test_poll_catches_up_without_notify(db, monkeypatch):
    maker, sa_engine = db
    engine = FlagEngine()

    async def no_listen():
        return None

    monkeypatch.setattr(engine, "_listen", no_listen)
    await engine.start(maker, sa_engine, poll_seconds=0.1)
    try:
        version = await _write_elsewhere(maker, AGENT_EDITOR)
        await _wait_for(engine, version)
        assert engine.is_enabled(AGENT_EDITOR) and engine.snapshot_age_seconds < 1
    finally:
        await engine.stop()


async def test_a_failed_refresh_keeps_the_last_good_snapshot(db):
    maker, sa_engine = db
    await _write_elsewhere(maker, AGENT_EDITOR)
    engine = FlagEngine()
    await engine.start(maker, sa_engine, poll_seconds=3600)
    try:
        assert engine.is_enabled(AGENT_EDITOR)
        async with maker() as session:
            await session.execute(text("ALTER TABLE feature_flags RENAME TO feature_flags_gone"))
            await session.commit()
        assert await engine.refresh() is False
        assert engine.is_enabled(AGENT_EDITOR)
        async with maker() as session:
            await session.execute(text("ALTER TABLE feature_flags_gone RENAME TO feature_flags"))
            await session.commit()
    finally:
        await engine.stop()


async def test_state_version_counts_every_write(db):
    maker, _ = db
    async with maker() as session:
        assert await FlagRepository(session).state_version() == 1
        assert await session.scalar(select(func.count()).select_from(FeatureFlag)) == 0
    await _write_elsewhere(maker, AGENT_EDITOR)
    async with maker() as session:
        assert await FlagRepository(session).state_version() == 2
