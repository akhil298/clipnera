"""Jobs queued in Postgres and run by ``python -m jobs.worker`` processes.

The API inserts a row and returns at once; workers claim rows with
``FOR UPDATE SKIP LOCKED``, so any number of them can share the table without
taking the same job. Pipelines then run outside the API process: their memory
is not the API's, a deploy can restart the API without killing them, and the
worker caps how many run at once.

With ``WORKER_IDLE_SHUTDOWN_SECONDS`` set, a worker that has had nothing to
run for that long powers its machine off; the API starts it again when a job
arrives (``jobs.wake``).

A running job's ``heartbeat_at`` is refreshed while it runs. If its worker
dies, the heartbeat stops and the job is claimed again once it is
``JOB_VISIBILITY_TIMEOUT_SECONDS`` stale, with ``attempt`` > 1 so a pipeline
resumes from its last finished step.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
from typing import Any

from sqlalchemy import text

from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from jobs.model import BackgroundJob
from jobs.queue import Job, run_job
from jobs.wake import has_pending_jobs, wake_worker

log = get_logger(__name__)

# How long an idle worker waits before looking for new rows.
POLL_SECONDS = 1.0
# Seconds before a failed job is tried again, multiplied by its attempt number.
RETRY_BACKOFF_SECONDS = 30
# Finished rows are kept this long for inspection, then deleted.
KEEP_FINISHED_DAYS = 7
PRUNE_EVERY_SECONDS = 3600

_CLAIM = text("""
UPDATE background_jobs
SET status = 'running', attempts = attempts + 1, locked_by = :worker,
    heartbeat_at = now(), updated_at = now()
WHERE id = (
    SELECT id FROM background_jobs
    WHERE attempts < :max_attempts AND (
        (status = 'queued' AND run_after <= now())
        OR (status = 'running' AND heartbeat_at < now() - make_interval(secs => :stale))
    )
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, kind, payload, attempts
""")

# Rows a dead worker left running after their last allowed attempt.
_EXPIRE = text("""
UPDATE background_jobs
SET status = 'failed', last_error = 'Worker stopped responding on the last attempt', updated_at = now()
WHERE status = 'running' AND attempts >= :max_attempts
  AND heartbeat_at < now() - make_interval(secs => :stale)
""")

_PRUNE = text("""
DELETE FROM background_jobs
WHERE status IN ('done', 'failed') AND updated_at < now() - make_interval(days => :days)
""")


class PostgresQueue:
    async def enqueue(self, job: Job) -> None:
        async with AsyncSessionLocal() as session:
            row = BackgroundJob(kind=job.kind, payload=json.dumps(job.payload))
            session.add(row)
            await session.commit()
        log.info("Job queued: kind=%s id=%s", job.kind, row.id)
        await wake_worker()


async def _execute(statement: Any, **params: Any) -> Any:
    async with AsyncSessionLocal() as session:
        result = await session.execute(statement, params)
        await session.commit()
        return result


class PostgresWorker:
    def __init__(self, concurrency: int, stale_seconds: int, max_attempts: int, idle_shutdown_seconds: int = 0) -> None:
        self._concurrency = max(1, concurrency)
        self._stale = max(30, stale_seconds)
        self._max_attempts = max(1, max_attempts)
        self._idle_shutdown = idle_shutdown_seconds
        self._idle_since: float | None = None
        self._name = f"{socket.gethostname()}:{os.getpid()}"
        self._stopping = asyncio.Event()
        self._running: set[asyncio.Task] = set()
        self._last_prune = 0.0
        self._draining = False
        self.drained = False

    def stop(self) -> None:
        self._stopping.set()

    def drain(self) -> None:
        """Take no new jobs, finish the running ones, then stop: how a deploy switches to new code without cutting an
        edit off (a cut-off edit started again from the beginning)."""
        log.info("Draining: %d job(s) running; no new jobs until they finish", len(self._running))
        self._draining = True

    async def run(self) -> None:
        log.info("Worker started: postgres queue, %d at once, name=%s", self._concurrency, self._name)
        while not self._stopping.is_set():
            try:
                await self.poll_once()
            except Exception:
                log.exception("Job poll failed; retrying")
                await self._idle()
        if self._running:
            log.info("Worker stopping; %d job(s) will be picked up again", len(self._running))
            for task in self._running:
                task.cancel()
            await asyncio.gather(*self._running, return_exceptions=True)

    async def poll_once(self) -> None:
        if self._draining:
            if self._running:
                await asyncio.wait(self._running, timeout=POLL_SECONDS)
                return
            log.info("Drained; stopping so the new code starts")
            self.drained = True
            self.stop()
            return
        if len(self._running) >= self._concurrency:
            await asyncio.wait(self._running, return_when=asyncio.FIRST_COMPLETED)
            return
        await self._housekeeping()
        row = (await _execute(_CLAIM, worker=self._name, max_attempts=self._max_attempts, stale=self._stale)).first()
        if row is None:
            if not self._running and await self._idle_too_long():
                await self._power_off()
                return
            await self._idle()
            return
        self._idle_since = None
        job = Job(kind=row.kind, payload=json.loads(row.payload), attempt=row.attempts)
        task = asyncio.create_task(self._handle(row.id, job))
        self._running.add(task)
        task.add_done_callback(self._running.discard)

    async def _idle(self) -> None:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=POLL_SECONDS)
        except asyncio.TimeoutError:
            pass

    async def _idle_too_long(self) -> bool:
        if self._idle_shutdown <= 0:
            return False
        now = asyncio.get_running_loop().time()
        if self._idle_since is None:
            self._idle_since = now
        # A queued retry waiting out its backoff is not idle. Running rows are
        # left out: with nothing of ours running they are stale, and the claim
        # or the expiry sweep deals with them.
        if await has_pending_jobs(include_running=False):
            self._idle_since = now
            return False
        return now - self._idle_since >= self._idle_shutdown

    async def _power_off(self) -> None:
        log.info("No jobs for %ds; powering the worker machine off", self._idle_shutdown)
        self.stop()
        process = await asyncio.create_subprocess_exec("sudo", "-n", "shutdown", "-h", "now")
        await process.wait()

    async def _housekeeping(self) -> None:
        now = asyncio.get_running_loop().time()
        if now - self._last_prune < PRUNE_EVERY_SECONDS:
            return
        self._last_prune = now
        await _execute(_EXPIRE, max_attempts=self._max_attempts, stale=self._stale)
        await _execute(_PRUNE, days=KEEP_FINISHED_DAYS)

    async def _handle(self, job_id: str, job: Job) -> None:
        heartbeat = asyncio.create_task(self._heartbeat(job_id))
        log.info("Job started: kind=%s id=%s attempt=%d", job.kind, job_id, job.attempt)
        try:
            await run_job(job)
        except asyncio.CancelledError:
            # Shutting down: hand the job back so the next worker resumes it.
            await asyncio.shield(_execute(
                text("UPDATE background_jobs SET status = 'queued', locked_by = NULL, updated_at = now() WHERE id = :id"),
                id=job_id,
            ))
            raise
        except Exception as exc:
            last = job.attempt >= self._max_attempts
            log.exception("Job failed: kind=%s id=%s attempt=%d%s", job.kind, job_id, job.attempt, "" if last else ", will retry")
            await _execute(
                text("""UPDATE background_jobs SET status = :status, last_error = :error, locked_by = NULL,
                        run_after = now() + make_interval(secs => :delay), updated_at = now() WHERE id = :id"""),
                status="failed" if last else "queued", error=f"{type(exc).__name__}: {exc}"[:4000],
                delay=RETRY_BACKOFF_SECONDS * job.attempt, id=job_id,
            )
        else:
            await _execute(
                text("UPDATE background_jobs SET status = 'done', locked_by = NULL, updated_at = now() WHERE id = :id"),
                id=job_id,
            )
            log.info("Job done: kind=%s id=%s", job.kind, job_id)
        finally:
            heartbeat.cancel()

    async def _heartbeat(self, job_id: str) -> None:
        while True:
            await asyncio.sleep(self._stale / 3)
            try:
                await _execute(text("UPDATE background_jobs SET heartbeat_at = now() WHERE id = :id"), id=job_id)
            except Exception as exc:
                log.warning("Could not refresh job heartbeat: %s", exc)


def worker_from_settings() -> PostgresWorker:
    settings = get_settings()
    return PostgresWorker(
        settings.JOB_WORKER_CONCURRENCY, settings.JOB_VISIBILITY_TIMEOUT_SECONDS, settings.JOB_MAX_ATTEMPTS,
        settings.WORKER_IDLE_SHUTDOWN_SECONDS,
    )
