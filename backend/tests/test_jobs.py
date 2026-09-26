from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from jobs import queue as job_queue
from jobs.queue import InProcessQueue, Job, handler, run_job
from jobs.worker import Worker
from pipeline import service as pipeline_service
from pipeline.model import PipelineStepType, StepStatus


class TestJob:
    def test_message_round_trip(self):
        job = Job("k", {"a": 1})
        assert Job.from_message(job.to_message(), attempt=3) == job
        assert Job.from_message(job.to_message(), attempt=3).attempt == 3

    @pytest.mark.asyncio
    async def test_unknown_kind_raises(self):
        with pytest.raises(LookupError):
            await run_job(Job("nobody-handles-this", {}))

    @pytest.mark.asyncio
    async def test_in_process_queue_runs_the_handler(self):
        seen = asyncio.Event()

        @handler("test.inprocess")
        async def _run(job):
            assert job.payload == {"x": 1}
            seen.set()

        await InProcessQueue().enqueue(Job("test.inprocess", {"x": 1}))
        await asyncio.wait_for(seen.wait(), 1)


class FakeSqs:
    def __init__(self, messages):
        self.messages = list(messages)
        self.deleted = []
        self.extended = []
        self.max_requested = []

    def receive_message(self, **kwargs):
        self.max_requested.append(kwargs["MaxNumberOfMessages"])
        batch, self.messages = self.messages[: kwargs["MaxNumberOfMessages"]], self.messages[kwargs["MaxNumberOfMessages"]:]
        return {"Messages": batch}

    def delete_message(self, QueueUrl, ReceiptHandle):
        self.deleted.append(ReceiptHandle)

    def change_message_visibility(self, QueueUrl, ReceiptHandle, VisibilityTimeout):
        self.extended.append(ReceiptHandle)


def message(kind, payload, receipt, count="1"):
    return {"Body": json.dumps({"kind": kind, "payload": payload}), "ReceiptHandle": receipt,
            "Attributes": {"ApproximateReceiveCount": count}}


class TestWorker:
    @pytest.mark.asyncio
    async def test_successful_jobs_are_deleted_and_failures_kept(self):
        attempts = []

        @handler("test.ok")
        async def _ok(job):
            attempts.append(job.attempt)

        @handler("test.boom")
        async def _boom(job):
            raise RuntimeError("boom")

        sqs = FakeSqs([message("test.ok", {}, "r1", "2"), message("test.boom", {}, "r2")])
        worker = Worker(sqs, "q", concurrency=2, visibility_timeout=30, wait_seconds=0)
        await worker.poll_once()
        await asyncio.gather(*list(worker._running))
        assert sqs.deleted == ["r1"] and attempts == [2]

    @pytest.mark.asyncio
    async def test_never_takes_more_than_its_free_slots(self):
        release = asyncio.Event()

        @handler("test.slow")
        async def _slow(job):
            await release.wait()

        sqs = FakeSqs([message("test.slow", {}, f"r{n}") for n in range(5)])
        worker = Worker(sqs, "q", concurrency=2, visibility_timeout=30, wait_seconds=0)
        await worker.poll_once()
        assert len(worker._running) == 2 and sqs.max_requested == [2]
        release.set()
        await worker.poll_once()  # waits for a slot instead of receiving
        await asyncio.gather(*list(worker._running))
        assert sqs.max_requested == [2]

    @pytest.mark.asyncio
    async def test_long_jobs_keep_their_message_hidden(self):
        release = asyncio.Event()

        @handler("test.long")
        async def _long(job):
            await release.wait()

        sqs = FakeSqs([message("test.long", {}, "r1")])
        worker = Worker(sqs, "q", concurrency=1, visibility_timeout=0.09, wait_seconds=0)
        await worker.poll_once()
        await asyncio.sleep(0.1)
        release.set()
        await asyncio.gather(*list(worker._running))
        assert "r1" in sqs.extended and sqs.deleted == ["r1"]


def run_payload(**overrides):
    payload = {
        "project_id": "p1", "source_url": "", "user": {"user_id": "u1"}, "resume": False,
        "steps": ["audio_extraction", "transcription"], "audio_config": {}, "watermark_enabled": True,
        "output_aspect_ratios": ["9:16"], "clip_settings": None, "is_pro": False, "credit_cost": 4,
    }
    return {**payload, **overrides}


class TestPipelineJob:
    def test_plan_job_is_plain_json(self):
        plan = pipeline_service._RunPlan(
            selected_steps=[PipelineStepType.TRANSCRIPTION], output_aspect_ratios=["9:16"], audio_config={},
            watermark_enabled=True, clip_settings=None, is_pro=True, credit_cost=6, refund=None,
        )
        job = plan.job(SimpleNamespace(id="p1", source_url=None), {"user_id": "u1"})
        assert job.kind == pipeline_service.PIPELINE_JOB
        assert json.loads(job.to_message())["payload"]["steps"] == ["transcription"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("resume", "attempt", "expected"), [(False, 1, False), (False, 2, True), (True, 1, True)])
    async def test_handler_rebuilds_the_run(self, monkeypatch, resume, attempt, expected):
        captured = {}

        async def fake_run(orchestrator, project_id, user, credit_refund_callback, requeue_on_interrupt):
            captured.update(orchestrator=orchestrator, project_id=project_id, refund=credit_refund_callback)

        monkeypatch.setattr(pipeline_service, "_run_pipeline", fake_run)
        await pipeline_service._run_pipeline_job(Job(pipeline_service.PIPELINE_JOB, run_payload(resume=resume), attempt=attempt))
        orchestrator = captured["orchestrator"]
        assert orchestrator._resume is expected
        assert orchestrator.selected_steps == [PipelineStepType.AUDIO_EXTRACTION, PipelineStepType.TRANSCRIPTION]
        assert captured["refund"].args == ("u1", "p1", 4, resume)
        pipeline_service._active_orchestrators.pop("p1", None)

    @pytest.mark.asyncio
    async def test_worker_shutdown_requeues_instead_of_failing(self):
        failed, refunded = [], []

        class Orchestrator:
            async def run(self):
                raise asyncio.CancelledError

            async def _mark_pipeline_failed(self, error):
                failed.append(error)

        async def refund():
            refunded.append(True)

        with pytest.raises(asyncio.CancelledError):
            await pipeline_service._run_pipeline(Orchestrator(), "p1", None, refund, requeue_on_interrupt=True)
        assert failed == [] and refunded == []


def stored_state(**fields):
    base = {"id": "s1", "is_completed": False, "error": None, "cancel_requested": False}
    return SimpleNamespace(**{**base, **fields})


class TestStoredProgress:
    def _patch(self, monkeypatch, state, logs=()):
        class Repo:
            async def get_pipeline(self, project_id):
                return state

            async def get_step_logs(self, pipeline_id):
                return list(logs)

        @asynccontextmanager
        async def session():
            yield None

        monkeypatch.setattr(pipeline_service, "AsyncSessionLocal", session)
        monkeypatch.setattr(pipeline_service, "_pipeline_repository", lambda _: Repo())

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("state", "status"), [
        (None, "idle"),
        (stored_state(is_completed=True), "completed"),
        (stored_state(error="boom"), "error"),
        (stored_state(error="Pipeline cancelled by user", cancel_requested=True), "cancelled"),
    ])
    async def test_terminal_states(self, monkeypatch, state, status):
        self._patch(monkeypatch, state)
        assert (await pipeline_service._stored_progress("p1"))["status"] == status

    @pytest.mark.asyncio
    async def test_running_step_progress(self, monkeypatch):
        running = SimpleNamespace(status=StepStatus.RUNNING, progress_percent=40, message="Transcribing", step=PipelineStepType.TRANSCRIPTION)
        self._patch(monkeypatch, stored_state(), [SimpleNamespace(status=StepStatus.COMPLETED), running])
        progress = await pipeline_service._stored_progress("p1")
        assert progress == {"status": "running", "percent": 40, "message": "Transcribing", "current_step": "transcription", "step_status": "running"}


class TestQueueSelection:
    def test_sqs_backend_needs_a_queue_url(self, monkeypatch):
        settings = SimpleNamespace(JOB_QUEUE_BACKEND="sqs", SQS_JOBS_QUEUE_URL="")
        monkeypatch.setattr(job_queue, "get_settings", lambda: settings)
        monkeypatch.setattr(job_queue, "_queue", None)
        with pytest.raises(RuntimeError):
            job_queue.get_queue()

    def test_default_is_in_process(self, monkeypatch):
        settings = SimpleNamespace(JOB_QUEUE_BACKEND="inprocess", SQS_JOBS_QUEUE_URL="")
        monkeypatch.setattr(job_queue, "get_settings", lambda: settings)
        monkeypatch.setattr(job_queue, "_queue", None)
        assert isinstance(job_queue.get_queue(), InProcessQueue)
