"""In-app notifications against a real Postgres database.

Skipped unless TEST_DATABASE_URL points at a disposable database, e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/clipnera_test pytest tests/test_notifications_db.py

Every table in that database is dropped and recreated.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main
import notifications.service
from auth.dependencies import get_current_user
from auth.model import User
from clip.model import ProjectStatus, VideoProject
from clip_generation.model import GeneratedClip
from core.database import Base, get_db
from notifications.broker import broker
from notifications.service import notify_pipeline_outcome

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
    pytest.mark.asyncio,
]


@pytest_asyncio.fixture
async def db(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(notifications.service, "AsyncSessionLocal", maker)

    async def _get_db():
        async with maker() as session:
            yield session

    def client(user_id: str) -> httpx.AsyncClient:
        main.app.dependency_overrides[get_db] = _get_db
        main.app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")

    yield SimpleNamespace(maker=maker, client=client)
    main.app.dependency_overrides.clear()
    await engine.dispose()


async def _project(maker, clips: int = 0) -> tuple[str, str]:
    async with maker() as session:
        user = User(id=str(uuid4()), email=f"{uuid4().hex[:8]}@test.dev")
        session.add(user)
        project = VideoProject(
            id=str(uuid4()), user_id=user.id, title="Podcast 12", source_type="upload", status=ProjectStatus.COMPLETED
        )
        session.add(project)
        await session.flush()
        for _ in range(clips):
            session.add(
                GeneratedClip(
                    id=str(uuid4()), project_id=project.id, user_id=user.id, title="Clip", start_time=0,
                    end_time=10, duration_seconds=10, s3_key=f"clips/{uuid4()}.mp4", s3_bucket="bucket",
                )
            )
        await session.commit()
        return user.id, project.id


async def test_pipeline_outcomes_land_in_the_inbox(db):
    user_id, project_id = await _project(db.maker, clips=3)
    await notify_pipeline_outcome(user_id, project_id, success=True)
    await notify_pipeline_outcome(user_id, project_id, success=False, refunded=True)

    async with db.client(user_id) as http:
        body = (await http.get("/api/v1/notifications")).json()

    assert body["error"] is None
    failed, completed = body["data"]["notifications"]
    assert completed["kind"] == "pipeline_completed"
    assert completed["project_id"] == project_id
    assert completed["message"] == '"Podcast 12" finished processing with 3 clip(s).'
    assert completed["read_at"] is None
    assert failed["kind"] == "pipeline_failed"
    assert failed["message"].endswith("Your credits were refunded.")


async def test_new_notifications_are_pushed_to_the_users_open_streams(db):
    user_id, project_id = await _project(db.maker, clips=2)
    other_id, _ = await _project(db.maker)

    async with broker.subscribe(user_id) as mine, broker.subscribe(other_id) as theirs:
        await notify_pipeline_outcome(user_id, project_id, success=True)
        event = mine.get_nowait()
        assert theirs.empty()

    async with db.client(user_id) as http:
        [stored] = (await http.get("/api/v1/notifications")).json()["data"]["notifications"]
    # The pushed event is exactly what the list endpoint returns.
    assert event == stored
    assert broker._subscribers == {}


async def test_read_all_and_clear_only_touch_the_callers_inbox(db):
    user_id, project_id = await _project(db.maker)
    other_id, other_project = await _project(db.maker)
    await notify_pipeline_outcome(user_id, project_id, success=True)
    await notify_pipeline_outcome(other_id, other_project, success=True)

    async with db.client(user_id) as http:
        read = (await http.post("/api/v1/notifications/read-all")).json()["data"]["notifications"]
        assert [n["read_at"] is not None for n in read] == [True]
        cleared = (await http.delete("/api/v1/notifications")).json()
        assert cleared["data"]["notifications"] == []

    async with db.client(other_id) as http:
        others = (await http.get("/api/v1/notifications")).json()["data"]["notifications"]
    assert len(others) == 1
    assert others[0]["read_at"] is None


async def test_a_notification_failure_never_raises(db, monkeypatch):
    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(notifications.service, "AsyncSessionLocal", broken)
    await notify_pipeline_outcome("nobody", "nothing", success=True)
