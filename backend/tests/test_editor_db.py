"""Editor projects against a real Postgres.

Skipped unless TEST_DATABASE_URL points at a disposable database (every table
in it is dropped and recreated), e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/clipnera_editor_test pytest tests/test_editor_db.py
"""

from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter
from sqlalchemy import select

from auth.model import User
from clients.ai.base import ToolCall
from core.exceptions import CustomException
from edit_engine.model import EditProject, EditStatus
from editor.agent_tools import EDITOR_TOOLS, EditorContext
from editor.history import Actor
from editor.model import EditorOp
from editor.ops import Op
from editor.schema import EditorProjectCreate
from editor.service import EditorService
from editor.timeline import TimelineError
import understanding.service
from test_plans_db import TEST_DATABASE_URL, db  # noqa: F401  the shared database fixture

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")]

OPS = TypeAdapter(list[Op])


class _NoQueue:
    async def enqueue(self, job) -> None:
        pass


@pytest.fixture(autouse=True)
def no_background_jobs(monkeypatch):
    # Adding an asset queues its analysis; the job would reach the real S3 and database.
    monkeypatch.setattr(understanding.service, "get_queue", _NoQueue)
def clip_asset(owner: str, project_id: str) -> dict:
    # Only files uploaded under the project's own folder may be added (editor.service.asset_prefix).
    key = f"editor/{owner}/{project_id}/a1.mp4"
    return {"op": "add_asset", "asset": {"id": "a1", "kind": "video", "key": key, "frames": 300, "has_audio": True}}


def clip(item_id: str, at: int) -> dict:
    return {"op": "add_item", "track": "v1", "item": {"type": "clip", "id": item_id, "asset": "a1", "at": at, "src_in": 0, "src_out": 90}}


async def user(maker, email: str = "creator@example.com") -> str:
    async with maker() as session:
        row = User(email=email)
        session.add(row)
        await session.commit()
        return row.id


async def test_a_new_project_is_an_empty_frame_of_the_chosen_shape(db) -> None:
    owner = await user(db)
    async with db() as session:
        project = await EditorService(session).create(owner, EditorProjectCreate(title=" Launch ", aspect="1:1"))
    assert (project.title, project.version, project.duration_s) == ("Launch", 0, 0)
    assert (project.timeline.width, project.timeline.height) == (1080, 1080)
    assert [t.id for t in project.timeline.tracks] == ["v1"]


async def test_each_batch_of_ops_is_one_logged_version(db) -> None:
    owner = await user(db)
    async with db() as session:
        service = EditorService(session)
        project = await service.create(owner, EditorProjectCreate())
        first = await service.apply(owner, project.id, 0, OPS.validate_python([clip_asset(owner, project.id), clip("c1", 0)]))
        # Different footage from c1: an agent may never repeat the same source (rule CT-08, never-do ND-05).
        agent_clip = {**clip("c2", 90), "item": {**clip("c2", 90)["item"], "src_in": 100, "src_out": 190}}
        second = await service.apply(owner, project.id, 1, OPS.validate_python([agent_clip]), Actor(author="agent:editor"))
    assert (first.version, second.version) == (1, 2)
    async with db() as session:
        reloaded = await EditorService(session).get(owner, project.id)
        log = (await session.execute(select(EditorOp).order_by(EditorOp.version))).scalars().all()
    assert reloaded.duration_s == 6.0
    assert [(row.version, row.author, len(json.loads(row.ops))) for row in log] == [(1, "user", 2), (2, "agent:editor", 1)]


async def test_a_version_the_project_never_had_is_refused_and_says_the_current_one(db) -> None:
    owner = await user(db)
    async with db() as session:
        service = EditorService(session)
        project = await service.create(owner, EditorProjectCreate())
        await service.apply(owner, project.id, 0, OPS.validate_python([clip_asset(owner, project.id)]))
        with pytest.raises(CustomException) as caught:
            await service.apply(owner, project.id, 5, OPS.validate_python([clip("c1", 0)]))
    assert (caught.value.code, caught.value.extra) == ("STALE_VERSION", {"version": 1})


async def test_a_bad_op_saves_nothing(db) -> None:
    owner = await user(db)
    async with db() as session:
        service = EditorService(session)
        project = await service.create(owner, EditorProjectCreate())
        with pytest.raises(TimelineError):
            await service.apply(owner, project.id, 0, OPS.validate_python([clip_asset(owner, project.id), clip("c1", 0), clip("c2", 30)]))
    async with db() as session:
        assert (await EditorService(session).get(owner, project.id)).version == 0
        assert (await session.execute(select(EditorOp))).first() is None


async def test_other_users_projects_are_not_found(db) -> None:
    owner, stranger = await user(db), await user(db, "stranger@example.com")
    async with db() as session:
        project = await EditorService(session).create(owner, EditorProjectCreate())
        with pytest.raises(CustomException) as caught:
            await EditorService(session).get(stranger, project.id)
    assert caught.value.code == "NOT_FOUND"


async def test_a_planned_reel_opens_as_a_project(db) -> None:
    owner = await user(db)
    compiled = {
        "duration": 2.0, "width": 1080, "height": 1920, "look": "vivid",
        "picture": [{"kind": "video", "src": 0, "in": 1.0, "out": 3.0, "at": 0.0, "zoom": 1.0, "crop_x": 0.4}],
        "voice": [{"src": 0, "in": 1.0, "out": 3.0, "at": 0.0}], "texts": [{"kind": "hook", "text": "Listen up", "at": 0.0, "dur": 1.5}],
        "sfx": [], "words": [{"word": "Hi", "start": 0.1, "end": 0.4}], "music": None,
    }
    sources = [{"key": "u/e/talk.mp4", "kind": "video", "name": "talk.mp4", "duration": 10.0, "width": 1920, "height": 1080, "has_audio": True}]
    async with db() as session:
        edit = EditProject(user_id=owner, title="Shoes", status=EditStatus.PLANNED, sources=json.dumps(sources),
                           timeline=json.dumps(compiled), caption_style="punch", language="hinglish")
        session.add(edit)
        await session.commit()
        project = await EditorService(session).import_reel(owner, edit.id)
    assert (project.title, project.timeline.look) == ("Shoes", "vivid")
    assert {t.id for t in project.timeline.tracks} == {"v1", "hook", "voice"}
    assert project.timeline.captions.style == "punch"


async def test_a_reel_without_an_edit_cannot_be_opened(db) -> None:
    owner = await user(db)
    async with db() as session:
        edit = EditProject(user_id=owner, title="Draft")
        session.add(edit)
        await session.commit()
        with pytest.raises(CustomException) as caught:
            await EditorService(session).import_reel(owner, edit.id)
    assert caught.value.code == "NOT_READY"


async def test_the_agent_reads_and_edits_through_its_tools(db) -> None:
    owner = await user(db)
    async with db() as session:
        service = EditorService(session)
        project = await service.create(owner, EditorProjectCreate())
        context = EditorContext(service, owner, project.id)
        await service.apply(owner, project.id, 0, OPS.validate_python([clip_asset(owner, project.id), clip("c1", 0), clip("c2", 90)]))
        refused = await EDITOR_TOOLS.call(context, ToolCall("1", "apply_edits", {"base_version": 1, "ops": [
            {"op": "trim_item", "item": "c1", "src_out": 120}]}))
        edited = await EDITOR_TOOLS.call(context, ToolCall("2", "apply_edits", {"base_version": 1, "human_owned_ok": ["c1"], "ops": [
            {"op": "update_item", "item": "c1", "patch": {"keyframes": {"scale": [{"f": 0, "v": 1}, {"f": 12, "v": 1.15}]}}}]}))
        seen = json.loads((await EDITOR_TOOLS.call(context, ToolCall("3", "get_timeline", {}))).content)
    assert refused.is_error and refused.content.startswith("OVERLAP") and '"op_index": 0' in refused.content
    assert not edited.is_error and seen["version"] == 2
    assert seen["tracks"][0]["items"][0]["keyframes"] == {"scale": [[0, 1.0], [12, 1.15]]}
    async with db() as session:
        authors = (await session.execute(select(EditorOp.author).order_by(EditorOp.version))).scalars().all()
    assert authors == ["user", "agent:editor"]
