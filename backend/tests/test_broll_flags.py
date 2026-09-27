"""B-Roll Studio features are admin switches: off means the API refuses and the pipeline skips."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

import main
from auth.dependencies import get_current_user
from core.exceptions import CustomException
from feature_flags.dependencies import get_feature_flag_service
from feature_flags.registry import BROLL_AI_SHOTS, BROLL_CUTAWAYS, BROLL_REELS, BROLL_STUDIO, FLAGS, VIDEO_UPLOAD
from feature_flags.service import resolve


class Flags:
    def __init__(self, *on: str):
        self.on = set(on)

    async def effective(self):
        return resolve({key: key in self.on for key in FLAGS})

    async def is_enabled(self, key):
        return (await self.effective())[key]

    async def require(self, *keys):
        effective = await self.effective()
        for key in keys:
            if not effective[key]:
                raise CustomException(message="off", code="FEATURE_DISABLED", status_code=403, extra={"feature": key})


@pytest.fixture
def client():
    def make(*on: str) -> TestClient:
        main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
        main.app.dependency_overrides[get_feature_flag_service] = lambda: Flags(*on)
        return TestClient(main.app, raise_server_exceptions=False)

    yield make
    main.app.dependency_overrides.clear()


GATED = [
    ("post", "/api/v1/uploads/video/init", VIDEO_UPLOAD),
    ("get", "/api/v1/reels", BROLL_REELS),
    ("post", "/api/v1/reels", BROLL_REELS),
    ("get", "/api/v1/broll/clips/clip-1", BROLL_CUTAWAYS),
    ("get", "/api/v1/broll/search?q=city", BROLL_CUTAWAYS),
]


@pytest.mark.parametrize(("method", "path", "flag"), GATED)
def test_everything_is_off_by_default(client, method, path, flag):
    kwargs = {"json": {}} if method == "post" else {}
    response = getattr(client(), method)(path, **kwargs)
    assert response.status_code == 403
    assert response.json()["error"] == "FEATURE_DISABLED" and response.json()["feature"] == flag


def test_a_child_switch_needs_the_main_switch(client):
    from reels.route import get_reel_service

    class Reels:
        async def list(self, user_id):
            return []

    assert client(BROLL_REELS).get("/api/v1/reels").status_code == 403
    api = client(BROLL_STUDIO, BROLL_REELS)
    main.app.dependency_overrides[get_reel_service] = lambda: Reels()
    response = api.get("/api/v1/reels")
    assert response.status_code == 200 and response.json()["data"] == []


def test_the_admin_library_stays_open(client):
    from auth.dependencies import get_current_admin
    from broll.route import get_broll_service
    from broll.schema import BrollAssetListResponse

    class Library:
        async def list_assets(self, *args):
            return BrollAssetListResponse(items=[], total=0)

    # Admins fill the library before launch; the admin gate, not the flag, decides.
    api = client()
    main.app.dependency_overrides[get_current_admin] = lambda: object()
    main.app.dependency_overrides[get_broll_service] = lambda: Library()
    response = api.get("/api/v1/admin/broll/assets")
    assert response.status_code == 200 and response.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_ai_shots_are_refused_when_switched_off(monkeypatch):
    from broll import generation

    monkeypatch.setattr(generation, "FeatureFlagService", lambda session: Flags(BROLL_STUDIO, BROLL_CUTAWAYS))
    with pytest.raises(CustomException) as err:
        await generation.start_generation(None, "u", "beach", "", {"type": "reel_scene", "id": "r", "index": 0})
    assert err.value.code == "FEATURE_DISABLED"


@pytest.mark.asyncio
async def test_pipeline_skips_cutaways_while_off(monkeypatch):
    from pipeline import service as pipeline_service

    planned = []

    @asynccontextmanager
    async def session():
        yield None

    async def plan(*args, **kwargs):
        planned.append(args)
        return 1

    monkeypatch.setattr(pipeline_service, "AsyncSessionLocal", session)
    monkeypatch.setattr(pipeline_service, "plan_project_broll", plan)
    orchestrator = pipeline_service.PipelineOrchestrator.__new__(pipeline_service.PipelineOrchestrator)
    orchestrator.project_id, orchestrator.user_id, orchestrator.is_pro = "p", "u", False
    orchestrator._notify = lambda *a, **k: None

    monkeypatch.setattr(pipeline_service, "FeatureFlagService", lambda s: Flags())
    await orchestrator._plan_broll()
    assert planned == []

    monkeypatch.setattr(pipeline_service, "FeatureFlagService", lambda s: Flags(BROLL_STUDIO, BROLL_CUTAWAYS))
    await orchestrator._plan_broll()
    assert len(planned) == 1
