"""The server starts the requested run once a YouTube download is stored, so a
reloaded or closed page cannot leave the project unprocessed."""

from __future__ import annotations

import pytest

from clip import service as clip_service
from clip.model import ProjectStatus
from core.exceptions import CustomException
from pipeline import service as pipeline_service
from pipeline.schema import PipelineStartRequest

STORED = {
    "s3_key": "k.mp4", "s3_bucket": "b", "presigned_url": "", "file_size": 100,
    "duration_seconds": 62, "local_path": None,
}


class FakeRepo:
    def __init__(self) -> None:
        self.status = None

    async def update_project_s3(self, project_id, s3_key, s3_bucket, presigned_url, file_size, duration, status, local_path=None):
        self.status = status


class FakeYouTube:
    async def download_and_store(self, url, user_id, project_id, format_id):
        return STORED

    @staticmethod
    def _format_bytes(size):
        return f"{size} B"


@pytest.fixture
def download(monkeypatch):
    progress: dict = {}
    started: list = []
    outcome = {"error": None}

    async def set_progress(key, data):
        progress[key] = data

    async def start(project_id, user_id, request):
        # The run must exist before the client is told the source is done.
        started.append((project_id, user_id, request.body(), progress.get(project_id)))
        return outcome["error"]

    monkeypatch.setattr(clip_service.YouTubeService, "set_progress", set_progress)
    monkeypatch.setattr(pipeline_service, "start_when_source_ready", start)
    repo = FakeRepo()
    service = clip_service.ClipService(repo)
    service._youtube = FakeYouTube()

    async def run(pipeline):
        await service._background_download("https://youtu.be/x", "u1", "p1", None, pipeline)
        return repo.status, progress.get("p1"), started

    run.outcome = outcome
    return run


@pytest.mark.asyncio
async def test_the_requested_run_starts_before_done_is_reported(download):
    status, progress, started = await download(PipelineStartRequest(steps=["transcription"]))
    assert status == ProjectStatus.UPLOADED
    assert started == [("p1", "u1", {"steps": ["transcription"]}, None)]
    assert progress["status"] == "done"


@pytest.mark.asyncio
async def test_without_a_request_nothing_is_started(download):
    status, progress, started = await download(None)
    assert status == ProjectStatus.UPLOADED and started == [] and progress["status"] == "done"


@pytest.mark.asyncio
async def test_a_run_that_cannot_start_reports_why(download):
    download.outcome["error"] = "Not enough credits"
    status, progress, _ = await download(PipelineStartRequest())
    assert status == ProjectStatus.UPLOADED
    assert progress["status"] == "error" and progress["message"] == "Not enough credits"


@pytest.mark.asyncio
async def test_start_when_source_ready_returns_the_refusal(monkeypatch):
    async def refuse(self, project_id, user, body):
        assert user == {"user_id": "u1"} and body == {"output_aspect_ratios": ["9:16"]}
        raise CustomException(message="Not enough credits", code="INSUFFICIENT_CREDITS", status_code=402)

    monkeypatch.setattr(pipeline_service.PipelineRunService, "start", refuse)
    request = PipelineStartRequest(output_aspect_ratios=["9:16"])
    assert await pipeline_service.start_when_source_ready("p1", "u1", request) == "Not enough credits"


@pytest.mark.asyncio
async def test_start_when_source_ready_is_none_once_started(monkeypatch):
    async def accept(self, project_id, user, body):
        return {"status": "started"}

    monkeypatch.setattr(pipeline_service.PipelineRunService, "start", accept)
    assert await pipeline_service.start_when_source_ready("p1", "u1", PipelineStartRequest()) is None
