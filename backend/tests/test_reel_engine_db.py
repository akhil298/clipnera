"""The premium footage reel through the product against a real Postgres: the Pro gate, credits taken up front,
the job finishing with its Edit Plan on the reel, the refund when it fails, and the asset registry.

The reel engine's AI pipeline is replaced by a stand-in that writes a short reel and a plan, so this runs
without model calls. Skipped unless TEST_DATABASE_URL points at a disposable database.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import notifications.service as notifications
import reel_engine.jobs as premium_jobs
import reel_engine.store as store_module
import edit_engine.service as service_module
from auth.model import User
from core.exceptions import CustomException
from edit_engine.model import EditProject, EditStatus
from edit_engine.schema import EditCreateRequest, EditSourceFile, EditSourcesCompleteRequest, EditSourcesInitRequest
from edit_engine.service import EditService
from reel_engine.assets import AssetRecord
from reel_engine.plan import Brief, EditPlan, LayerScore, Progress, Review, VideoItem
from reel_engine.store import DbAssetStore
from subscription.model import PlanSlug
from subscription.service import SubscriptionService
from test_edit_engine_db import FakeS3
from test_plans_db import TEST_DATABASE_URL, db  # noqa: F401  the shared database fixture

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg"),
]


def _video(folder: Path) -> Path:
    path = folder / "raw.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=4",
                    "-c:v", "libx264", "-preset", "ultrafast", str(path)], check=True)
    return path


@pytest.fixture
def world(db, monkeypatch, tmp_path):  # noqa: F811
    FakeS3.root = tmp_path / "s3"
    queued, pro_users = [], set()

    class Queue:
        async def enqueue(self, job):
            queued.append(job)

    original = SubscriptionService.get_effective_plan

    async def plan(self, user_id):
        return PlanSlug.PRO.value if user_id in pro_users else await original(self, user_id)

    for module in (premium_jobs, notifications, store_module):
        monkeypatch.setattr(module, "AsyncSessionLocal", db)
    monkeypatch.setattr(premium_jobs, "S3", FakeS3)
    monkeypatch.setattr(store_module, "S3", FakeS3)
    monkeypatch.setattr(service_module, "get_queue", lambda: Queue())
    monkeypatch.setattr(SubscriptionService, "get_effective_plan", plan)
    return {"db": db, "queued": queued, "pro": pro_users, "tmp": tmp_path}


async def _user(world, pro: bool, email: str) -> str:
    async with world["db"]() as session:
        user = User(email=email)
        session.add(user)
        await session.commit()
        await SubscriptionService.for_session(session).activate_free_plan(user.id)
        await SubscriptionService.for_session(session).grant_purchased_credits(user.id, 500, "test", reference_id=f"t-{email}")
    if pro:
        world["pro"].add(user.id)
    return user.id


async def _balance(world, user_id: str) -> int:
    async with world["db"]() as session:
        return await SubscriptionService.for_session(session).get_user_credit_balance(user_id)


async def _premium_edit(world, user_id: str) -> str:
    video = _video(world["tmp"])
    async with world["db"]() as session:
        service = EditService(session, FakeS3())
        edit = await service.create(user_id, EditCreateRequest(title="Untitled reel", engine="premium", intent="make it punchy"))
        uploads = await service.init_sources(user_id, edit.id, EditSourcesInitRequest(files=[
            EditSourceFile(filename="raw.mp4", content_type="video/mp4", size_bytes=video.stat().st_size, duration_s=4)]))
        shutil.copy(video, uploads.uploads[0].url.removeprefix("file://"))
        await service.complete_sources(user_id, edit.id, EditSourcesCompleteRequest(keys=[u.key for u in uploads.uploads]))
        started = await service.analyze(user_id, edit.id)
        assert started.status == "analyzing" and started.engine == "premium"
        assert started.premium and started.premium.stage == "queued"
    return edit.id


async def test_premium_needs_pro(world):
    user_id = await _user(world, pro=False, email="free@example.com")
    async with world["db"]() as session:
        with pytest.raises(CustomException) as caught:
            await EditService(session, FakeS3()).create(user_id, EditCreateRequest(engine="premium"))
    assert caught.value.code == "PRO_REQUIRED"


async def test_premium_edit_charges_up_front_and_lands_its_plan(world, monkeypatch):
    user_id = await _user(world, pro=True, email="pro@example.com")
    before = await _balance(world, user_id)
    seen = {}

    async def fake_run(inputs, work, out, store, owner="", brief="", target_seconds=0.0, passes=2, on_progress=None):
        seen.update(inputs=inputs, brief=brief, owner=owner, store=store)
        plan = EditPlan(brief=Brief(path="visual", audio_kind="silent", recipe="recipe_process", target_seconds=0,
                                    title_lead="Sunday", title_text="pancakes"),
                        video=[VideoItem(id="v0", src=0, t0=0, t1=2, out0=0, out1=2)], duration=2.0,
                        review=Review(scores=[LayerScore(layer="hook", score=8)], overall=8.0, passes=1),
                        progress=[Progress(stage="ingest"), Progress(stage="done")])
        if on_progress:
            await on_progress(plan)
        shutil.copy(inputs[0], out)
        return plan

    monkeypatch.setattr(premium_jobs.pipeline, "run", fake_run)
    edit_id = await _premium_edit(world, user_id)
    charged = before - await _balance(world, user_id)
    assert charged > 0
    job = world["queued"].pop()
    assert job.kind == premium_jobs.PREMIUM_JOB and job.payload["credits"] == charged
    await premium_jobs.premium_edit(job)

    assert seen["brief"] == "make it punchy" and seen["owner"] == user_id and isinstance(seen["store"], DbAssetStore)
    async with world["db"]() as session:
        edit = await EditService(session, FakeS3()).get(user_id, edit_id)
    assert edit.status == "done" and edit.output_url and edit.title == "Sunday pancakes"
    assert edit.premium.overall == 8.0 and edit.premium.recipe == "recipe_process" and edit.premium.stage == "done"
    assert edit.credits_charged == charged and edit.credits_estimate == 0


async def test_a_failed_premium_edit_is_refunded(world, monkeypatch):
    user_id = await _user(world, pro=True, email="pro2@example.com")
    before = await _balance(world, user_id)

    async def broken(*args, **kwargs):
        raise RuntimeError("renderer crashed")

    monkeypatch.setattr(premium_jobs.pipeline, "run", broken)
    edit_id = await _premium_edit(world, user_id)
    await premium_jobs.premium_edit(world["queued"].pop())
    assert await _balance(world, user_id) == before
    async with world["db"]() as session:
        edit = await session.get(EditProject, edit_id)
    assert edit.status == EditStatus.FAILED and edit.credits_charged == 0 and "refunded" in edit.error


async def test_registry_keeps_made_assets_by_scope(world):
    owner = await _user(world, pro=True, email="pro3@example.com")
    store = DbAssetStore(FakeS3())
    file = world["tmp"] / "sizzle.wav"
    file.write_bytes(b"RIFF" + b"0" * 200)
    await store.add(AssetRecord(kind="sfx", scope="global", words=["sizzle"], source="test"), file)
    await store.add(AssetRecord(kind="score", scope="user", owner=owner, words=["score"], source="test"), file)
    found = await store.search("sfx", {"sizzle"}, "someone-else")
    assert found and Path(await store.local(found[0], world["tmp"])).exists()
    assert await store.search("score", {"score"}, owner)
    assert not await store.search("score", {"score"}, "someone-else")
    await store.used([found[0].id])
    assert (await store.search("sfx", {"sizzle"}, owner))[0].uses == 1
    assert json.dumps(found[0].model_dump())
