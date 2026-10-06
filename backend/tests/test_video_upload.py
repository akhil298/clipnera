from __future__ import annotations

import math
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from clip import source_video
from clip.model import ProjectStatus
from core.exceptions import CustomException
from pipeline.schema import PipelineStartRequest
from uploads import service as upload_service
from uploads.schema import (
    VideoUploadAbortRequest,
    VideoUploadCompleteRequest,
    VideoUploadInitRequest,
)
from uploads.service import VideoUploadService, part_size_for, title_from_filename

MIB = 1024 * 1024


class FakeRepo:
    def __init__(self):
        self.projects: dict[str, SimpleNamespace] = {}

    async def create_project(self, user_id, title, source_type, source_url=None, status=ProjectStatus.PENDING):
        project = SimpleNamespace(
            id=f"p{len(self.projects) + 1}", user_id=user_id, title=title, source_type=source_type,
            status=status, s3_key=None, s3_bucket=None, file_size=None, duration_seconds=None, local_path=None,
        )
        self.projects[project.id] = project
        return project

    async def get_project(self, project_id, user_id):
        project = self.projects.get(project_id)
        return project if project and project.user_id == user_id else None

    async def update_project_status(self, project_id, status):
        self.projects[project_id].status = status

    async def update_project_s3(self, project_id, s3_key, s3_bucket, presigned_url, file_size, duration, status, local_path=None):
        project = self.projects[project_id]
        project.s3_key, project.s3_bucket, project.file_size = s3_key, s3_bucket, file_size
        project.duration_seconds, project.status = duration, status
        if local_path is not None:
            project.local_path = local_path

    async def delete_project(self, project_id, user_id):
        return self.projects.pop(project_id, None) is not None


class FakeS3:
    def __init__(self, stored_size=None):
        self.stored_size = stored_size
        self.completed = None
        self.deleted = []
        self.aborted = []

    def create_multipart_upload(self, bucket, key, content_type):
        return "up-1"

    def presign_upload_part(self, bucket, key, upload_id, part_number, expires_in=3600):
        return f"https://s3/{key}?part={part_number}"

    def complete_multipart_upload(self, bucket, key, upload_id, parts):
        self.completed = (upload_id, parts)

    def object_size(self, bucket, key):
        return self.stored_size

    def delete_object(self, bucket, key):
        self.deleted.append(key)

    def abort_multipart_upload(self, bucket, key, upload_id):
        self.aborted.append(upload_id)

    def download_file(self, bucket, key, file_path):
        Path(file_path).write_bytes(b"video")


class FakeSubscriptions:
    def __init__(self, max_seconds=1800):
        self.max_seconds = max_seconds

    async def get_entitlements(self, user_id):
        return SimpleNamespace(plan="free", max_upload_duration_seconds=self.max_seconds)


def make_service(s3=None, max_seconds=1800):
    repo = FakeRepo()
    return VideoUploadService(repo, FakeSubscriptions(max_seconds), s3 or FakeS3()), repo


def init_request(**overrides):
    fields = {"filename": "My Talk.mov", "content_type": "video/quicktime", "size_bytes": 40 * MIB}
    return VideoUploadInitRequest(**{**fields, **overrides})


class TestHelpers:
    def test_small_files_use_the_minimum_part(self):
        assert part_size_for(40 * MIB, 16 * MIB) == 16 * MIB

    def test_huge_files_stay_within_the_part_limit(self):
        size = 300 * 1024 * MIB
        part = part_size_for(size, 16 * MIB)
        assert part % MIB == 0 and math.ceil(size / part) <= 10_000

    def test_title_drops_the_extension(self):
        assert title_from_filename("My Talk.final.mov") == "My Talk.final"
        assert title_from_filename(".mp4") == "Uploaded video"


class TestSchema:
    def test_rejects_non_video_types(self):
        with pytest.raises(ValidationError):
            init_request(content_type="image/png")

    def test_rejects_duplicate_parts_and_sorts_the_rest(self):
        with pytest.raises(ValidationError):
            VideoUploadCompleteRequest(upload_id="u", parts=[{"part_number": 1, "etag": "a"}, {"part_number": 1, "etag": "b"}])
        request = VideoUploadCompleteRequest(upload_id="u", parts=[{"part_number": 2, "etag": "b"}, {"part_number": 1, "etag": "a"}])
        assert [p.part_number for p in request.parts] == [1, 2]


class TestInit:
    @pytest.mark.asyncio
    async def test_creates_a_pending_project_with_one_url_per_part(self):
        service, repo = make_service()
        result = await service.init("u1", init_request())
        project = repo.projects[result.project_id]
        assert project.status == ProjectStatus.PENDING and project.source_type == "upload"
        assert project.title == "My Talk" and project.file_size == 40 * MIB
        assert project.s3_key == f"videos/u1/{project.id}/source.mov"
        assert result.upload_id == "up-1" and result.part_size == 16 * MIB
        assert len(result.part_urls) == 3

    @pytest.mark.asyncio
    async def test_refuses_files_over_the_size_limit(self):
        service, repo = make_service()
        with pytest.raises(CustomException) as err:
            await service.init("u1", init_request(size_bytes=service._settings.UPLOAD_MAX_BYTES + 1))
        assert err.value.status_code == 413 and not repo.projects

    @pytest.mark.asyncio
    async def test_refuses_videos_longer_than_the_plan_allows(self):
        service, repo = make_service(max_seconds=1800)
        with pytest.raises(CustomException) as err:
            await service.init("u1", init_request(duration_seconds=1801))
        assert err.value.code == "DURATION_NOT_ENTITLED" and not repo.projects


class TestComplete:
    async def _started(self, s3):
        service, repo = make_service(s3)
        result = await service.init("u1", init_request())
        return service, repo, result.project_id

    @pytest.mark.asyncio
    async def test_marks_the_project_processing(self):
        s3 = FakeS3(stored_size=40 * MIB)
        service, repo, project_id = await self._started(s3)
        request = VideoUploadCompleteRequest(upload_id="up-1", parts=[{"part_number": n, "etag": f"e{n}"} for n in (3, 1, 2)])
        result = await service.complete("u1", project_id, request)
        assert result.status == "processing" and repo.projects[project_id].status == ProjectStatus.PROCESSING
        assert [p["PartNumber"] for p in s3.completed[1]] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_a_short_object_is_deleted_and_failed(self):
        s3 = FakeS3(stored_size=10)
        service, repo, project_id = await self._started(s3)
        with pytest.raises(CustomException) as err:
            await service.complete("u1", project_id, VideoUploadCompleteRequest(upload_id="up-1", parts=[{"part_number": 1, "etag": "e"}]))
        assert err.value.code == "UPLOAD_SIZE_MISMATCH"
        assert s3.deleted and repo.projects[project_id].status == ProjectStatus.FAILED

    @pytest.mark.asyncio
    async def test_another_users_upload_is_not_found(self):
        service, _, project_id = await self._started(FakeS3(stored_size=40 * MIB))
        with pytest.raises(CustomException) as err:
            await service.complete("u2", project_id, VideoUploadCompleteRequest(upload_id="up-1", parts=[{"part_number": 1, "etag": "e"}]))
        assert err.value.status_code == 404

    @pytest.mark.asyncio
    async def test_a_finished_upload_cannot_complete_twice(self):
        service, _, project_id = await self._started(FakeS3(stored_size=40 * MIB))
        request = VideoUploadCompleteRequest(upload_id="up-1", parts=[{"part_number": 1, "etag": "e"}])
        await service.complete("u1", project_id, request)
        with pytest.raises(CustomException) as err:
            await service.complete("u1", project_id, request)
        assert err.value.status_code == 409

    @pytest.mark.asyncio
    async def test_abort_removes_the_project(self):
        s3 = FakeS3()
        service, repo, project_id = await self._started(s3)
        await service.abort("u1", project_id, VideoUploadAbortRequest(upload_id="up-1"))
        assert s3.aborted == ["up-1"] and project_id not in repo.projects


class TestLocalCopy:
    @pytest.mark.asyncio
    async def test_an_existing_local_file_is_used_as_is(self, tmp_path):
        local = tmp_path / "v.mp4"
        local.write_bytes(b"x")
        project = SimpleNamespace(id="p", local_path=str(local), s3_bucket="b", s3_key="k.mp4")
        assert await source_video.ensure_local_copy(project, FakeS3()) == str(local)

    @pytest.mark.asyncio
    async def test_a_missing_file_is_fetched_from_s3(self, tmp_path, monkeypatch):
        monkeypatch.setattr(source_video, "DOWNLOAD_DIR", tmp_path)
        project = SimpleNamespace(id="p9", local_path="/gone.mp4", s3_bucket="b", s3_key="videos/u/p9/source.mov")
        path = await source_video.ensure_local_copy(project, FakeS3())
        assert path == str(tmp_path / "p9.mov") and Path(path).read_bytes() == b"video"
        assert not list(tmp_path.glob("*.part"))

    @pytest.mark.asyncio
    async def test_no_source_anywhere_is_none(self):
        project = SimpleNamespace(id="p", local_path=None, s3_bucket=None, s3_key=None)
        assert await source_video.ensure_local_copy(project, FakeS3()) is None


class TestPrepare:
    def _patch(self, monkeypatch, repo, duration):
        @asynccontextmanager
        async def session():
            yield None

        class S3:
            def generate_presigned_url(self, bucket, key):
                return f"https://s3/{bucket}/{key}"

        async def probe(self, path):
            probed.append(path)
            return duration

        async def set_progress(key, data):
            progress[key] = data

        progress: dict = {}
        probed: list[str] = []
        monkeypatch.setattr(upload_service, "AsyncSessionLocal", session)
        monkeypatch.setattr(upload_service, "ClipRepository", lambda _: repo)
        monkeypatch.setattr(upload_service, "S3", S3)
        monkeypatch.setattr(upload_service.FFmpegService, "probe_duration", probe)
        monkeypatch.setattr(upload_service.YouTubeService, "set_progress", set_progress)
        progress["probed"] = probed
        return progress

    async def _processing_project(self, repo):
        project = await repo.create_project("u1", "t", "upload", status=ProjectStatus.PROCESSING)
        project.s3_key, project.s3_bucket, project.file_size = "k.mp4", "b", 100
        return project

    @pytest.mark.asyncio
    async def test_a_readable_video_becomes_uploaded(self, monkeypatch):
        repo = FakeRepo()
        project = await self._processing_project(repo)
        progress = self._patch(monkeypatch, repo, 61.2)
        await upload_service.prepare_uploaded_video(project.id, "u1")
        assert project.status == ProjectStatus.UPLOADED and project.duration_seconds == 62
        assert progress["probed"] == ["https://s3/b/k.mp4"] and project.local_path is None
        assert progress[project.id]["status"] == "done"

    @pytest.mark.asyncio
    async def test_an_unreadable_video_fails_with_a_message(self, monkeypatch):
        repo = FakeRepo()
        project = await self._processing_project(repo)
        progress = self._patch(monkeypatch, repo, 0.0)
        await upload_service.prepare_uploaded_video(project.id, "u1")
        assert project.status == ProjectStatus.FAILED and progress[project.id]["status"] == "error"

    def _patch_start(self, monkeypatch, progress, error):
        from pipeline import service as pipeline_service

        started = []

        async def start(project_id, user_id, request):
            # The run must exist before the client is told the source is done.
            started.append((project_id, user_id, request.body(), progress.get(project_id)))
            return error

        monkeypatch.setattr(pipeline_service, "start_when_source_ready", start)
        return started

    @pytest.mark.asyncio
    async def test_the_requested_run_starts_before_done_is_reported(self, monkeypatch):
        repo = FakeRepo()
        project = await self._processing_project(repo)
        progress = self._patch(monkeypatch, repo, 61.2)
        started = self._patch_start(monkeypatch, progress, error=None)
        request = PipelineStartRequest(steps=["transcription"], output_aspect_ratios=["9:16"])
        await upload_service.prepare_uploaded_video(project.id, "u1", request)
        assert started == [(project.id, "u1", {"steps": ["transcription"], "output_aspect_ratios": ["9:16"]}, None)]
        assert progress[project.id]["status"] == "done"

    @pytest.mark.asyncio
    async def test_a_run_that_cannot_start_reports_why(self, monkeypatch):
        repo = FakeRepo()
        project = await self._processing_project(repo)
        progress = self._patch(monkeypatch, repo, 61.2)
        self._patch_start(monkeypatch, progress, error="Not enough credits")
        await upload_service.prepare_uploaded_video(project.id, "u1", PipelineStartRequest())
        assert project.status == ProjectStatus.UPLOADED
        assert progress[project.id] == upload_service._progress("error", "Not enough credits")


class TestPipelineSource:
    def _orchestrator(self, monkeypatch, project, fetched_path):
        from pipeline import service as pipeline_service

        saved = {}

        class Repo:
            def __init__(self, _):
                pass

            async def get_project(self, project_id, user_id):
                return project

            async def set_local_path(self, project_id, path):
                saved[project_id] = path

        @asynccontextmanager
        async def session():
            yield None

        async def local_copy(p):
            return fetched_path

        monkeypatch.setattr(pipeline_service, "AsyncSessionLocal", session)
        monkeypatch.setattr(pipeline_service, "ClipRepository", Repo)
        monkeypatch.setattr(pipeline_service, "ensure_local_copy", local_copy)
        orchestrator = pipeline_service.PipelineOrchestrator.__new__(pipeline_service.PipelineOrchestrator)
        orchestrator.project_id, orchestrator.user_id = "p1", "u1"
        return orchestrator, saved

    @pytest.mark.asyncio
    async def test_a_fetched_source_is_remembered(self, monkeypatch):
        project = SimpleNamespace(id="p1", local_path=None)
        orchestrator, saved = self._orchestrator(monkeypatch, project, "/cache/p1.mp4")
        assert await orchestrator._project_video_path() == "/cache/p1.mp4"
        assert saved == {"p1": "/cache/p1.mp4"}

    @pytest.mark.asyncio
    async def test_an_existing_local_copy_is_not_rewritten(self, monkeypatch):
        project = SimpleNamespace(id="p1", local_path="/cache/p1.mp4")
        orchestrator, saved = self._orchestrator(monkeypatch, project, "/cache/p1.mp4")
        assert await orchestrator._project_video_path() == "/cache/p1.mp4" and saved == {}
