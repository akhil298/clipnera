"""Workspace team management against a real Postgres database.

Skipped unless TEST_DATABASE_URL points at a disposable database, e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/clipnera_ws_test pytest tests/test_workspace_db.py

Every table in that database is dropped and recreated.
"""

from __future__ import annotations

import os
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main
import subscription.service
from auth.dependencies import get_current_user
from auth.model import User, UserRole
from core.database import Base, get_db

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
    pytest.mark.asyncio,
]

PRO_EMAIL = "owner@example.com"


@pytest_asyncio.fixture
async def maker(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    # Team members are Pro-only; the always-pro list makes the owner Pro.
    monkeypatch.setattr(subscription.service, "AsyncSessionLocal", maker)
    monkeypatch.setattr(subscription.service, "pro_override_emails", lambda: frozenset({PRO_EMAIL}))
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def api(maker):
    async def _get_db():
        async with maker() as session:
            yield session

    def make(user_id: str) -> httpx.AsyncClient:
        main.app.dependency_overrides[get_db] = _get_db
        main.app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")

    yield make
    main.app.dependency_overrides.clear()


async def _user(maker, email: str | None = None) -> str:
    async with maker() as session:
        user = User(email=email or f"{uuid4().hex[:8]}@example.com", full_name="Test User")
        session.add(user)
        await session.commit()
        return user.id


def _new_member(role: str = "member") -> dict:
    return {"email": f"{uuid4().hex[:8]}@example.com", "password": "password123", "full_name": "New Member", "role": role}


async def _default_workspace(client: httpx.AsyncClient) -> str:
    response = await client.get("/api/v1/workspaces")
    assert response.status_code == 200
    (workspace,) = response.json()
    assert workspace["role"] == "owner"
    return workspace["id"]


async def test_first_listing_creates_one_personal_workspace(maker, api):
    client = api(await _user(maker, PRO_EMAIL))
    workspace_id = await _default_workspace(client)
    assert await _default_workspace(client) == workspace_id


async def test_owner_adds_member_as_regular_user(maker, api):
    client = api(await _user(maker, PRO_EMAIL))
    workspace_id = await _default_workspace(client)

    body = _new_member("viewer")
    response = await client.post(f"/api/v1/workspaces/{workspace_id}/members/create", json=body)
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "viewer"
    assert response.json()["status"] == "active"

    async with maker() as session:
        created = (await session.execute(select(User).where(User.email == body["email"]))).scalar_one()
    assert created.role == UserRole.USER

    members = (await client.get(f"/api/v1/workspaces/{workspace_id}/members")).json()
    assert {m["email"]: m["role"] for m in members}[body["email"]] == "viewer"
    assert (await client.get("/api/v1/workspaces")).json()[0]["member_count"] == 2


@pytest.mark.parametrize("role", ["admin", "owner"])
async def test_manager_roles_cannot_be_assigned(maker, api, role):
    client = api(await _user(maker, PRO_EMAIL))
    workspace_id = await _default_workspace(client)

    create = await client.post(f"/api/v1/workspaces/{workspace_id}/members/create", json=_new_member(role))
    invite = await client.post(f"/api/v1/workspaces/{workspace_id}/members", json={"email": "x@example.com", "role": role})
    assert create.status_code == 422
    assert invite.status_code == 422

    member = (await client.post(f"/api/v1/workspaces/{workspace_id}/members/create", json=_new_member())).json()
    promote = await client.patch(f"/api/v1/workspaces/{workspace_id}/members/{member['id']}", json={"role": role})
    assert promote.status_code == 422


async def test_non_owners_cannot_manage_members(maker, api):
    owner = api(await _user(maker, PRO_EMAIL))
    workspace_id = await _default_workspace(owner)
    body = _new_member()
    member = (await owner.post(f"/api/v1/workspaces/{workspace_id}/members/create", json=body)).json()

    # A member of the workspace can view the roster but not change it.
    async with maker() as session:
        member_user_id = (await session.execute(select(User.id).where(User.email == body["email"]))).scalar_one()
    teammate = api(member_user_id)
    assert (await teammate.get(f"/api/v1/workspaces/{workspace_id}/members")).status_code == 200
    add = await teammate.post(f"/api/v1/workspaces/{workspace_id}/members/create", json=_new_member())
    assert add.status_code in (403, 404)  # 403 once Pro-gated through, never 201

    # A stranger can't even see it.
    stranger = api(await _user(maker))
    assert (await stranger.get(f"/api/v1/workspaces/{workspace_id}/members")).status_code == 404
    assert (await stranger.delete(f"/api/v1/workspaces/{workspace_id}/members/{member['id']}")).status_code == 404


async def test_owner_row_cannot_be_changed_or_removed(maker, api):
    client = api(await _user(maker, PRO_EMAIL))
    workspace_id = await _default_workspace(client)
    members = (await client.get(f"/api/v1/workspaces/{workspace_id}/members")).json()
    owner_row = next(m for m in members if m["role"] == "owner")

    demote = await client.patch(f"/api/v1/workspaces/{workspace_id}/members/{owner_row['id']}", json={"role": "viewer"})
    remove = await client.delete(f"/api/v1/workspaces/{workspace_id}/members/{owner_row['id']}")
    assert demote.status_code == 403
    assert remove.status_code == 403
