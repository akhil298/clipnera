"""The Postgres job queue against a real database.

Skipped unless TEST_DATABASE_URL points at a disposable database; the
background_jobs table there is dropped and recreated.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jobs.postgres as pg
import jobs.wake as wake
from jobs.model import BackgroundJob
from jobs.queue import Job, handler

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
    pytest.mark.asyncio,
]

seen: list[tuple[str, int]] = []


@handler("test.pg_ok")
async def _ok(job: Job) -> None:
    await asyncio.sleep(0.2)
    seen.append((job.payload["name"], job.attempt))


@handler("test.pg_boom")
async def _boom(job: Job) -> None:
    raise RuntimeError("boom")


@pytest_asyncio.fixture
async def db(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: BackgroundJob.__table__.drop(c, checkfirst=True))
        await conn.run_sync(lambda c: BackgroundJob.__table__.create(c))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(pg, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(wake, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(pg, "POLL_SECONDS", 0.05)
    monkeypatch.setattr(pg, "RETRY_BACKOFF_SECONDS", 0)
    seen.clear()
    yield engine
    await engine.dispose()


async def _rows(engine) -> list:
    async with engine.connect() as conn:
        return (await conn.execute(text("SELECT kind, status, attempts, last_error FROM background_jobs ORDER BY created_at"))).all()


async def _drain(worker: pg.PostgresWorker, until, timeout: float = 10.0) -> None:
    task = asyncio.create_task(worker.run())
    try:
        async with asyncio.timeout(timeout):
            while not await until():
                await asyncio.sleep(0.05)
    finally:
        worker.stop()
        await task


async def test_jobs_run_in_parallel_and_finish(db):
    for name in ("a", "b", "c", "d"):
        await pg.PostgresQueue().enqueue(Job("test.pg_ok", {"name": name}))
    worker = pg.PostgresWorker(concurrency=4, stale_seconds=60, max_attempts=3)
    started = asyncio.get_running_loop().time()

    async def all_done():
        return all(row.status == "done" for row in await _rows(db))

    await _drain(worker, all_done)
    assert sorted(name for name, _ in seen) == ["a", "b", "c", "d"]
    # Four 0.2s jobs at once take about 0.2s, not 0.8s.
    assert asyncio.get_running_loop().time() - started < 0.75


async def test_a_failing_job_is_retried_then_given_up(db):
    await pg.PostgresQueue().enqueue(Job("test.pg_boom", {}))
    worker = pg.PostgresWorker(concurrency=1, stale_seconds=60, max_attempts=2)

    async def failed():
        return (await _rows(db))[0].status == "failed"

    await _drain(worker, failed)
    row = (await _rows(db))[0]
    assert row.attempts == 2
    assert "boom" in row.last_error


async def test_a_dead_workers_job_is_picked_up_again_as_a_resume(db):
    async with db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO background_jobs (id, kind, payload, status, attempts, heartbeat_at)
            VALUES ('dead', 'test.pg_ok', :payload, 'running', 1, now() - interval '10 minutes')
        """), {"payload": json.dumps({"name": "resumed"})})
    worker = pg.PostgresWorker(concurrency=1, stale_seconds=60, max_attempts=3)

    async def done():
        return (await _rows(db))[0].status == "done"

    await _drain(worker, done)
    assert seen == [("resumed", 2)]


async def test_two_workers_never_take_the_same_job(db):
    for index in range(6):
        await pg.PostgresQueue().enqueue(Job("test.pg_ok", {"name": str(index)}))
    workers = [pg.PostgresWorker(concurrency=2, stale_seconds=60, max_attempts=3) for _ in range(2)]
    tasks = [asyncio.create_task(w.run()) for w in workers]

    async with asyncio.timeout(10):
        while not all(row.status == "done" for row in await _rows(db)):
            await asyncio.sleep(0.05)
    for w in workers:
        w.stop()
    await asyncio.gather(*tasks)
    assert sorted(name for name, _ in seen) == [str(i) for i in range(6)]


async def test_an_idle_worker_powers_off_once_nothing_is_queued(db, monkeypatch):
    powered_off = asyncio.Event()

    async def power_off(self):
        self.stop()
        powered_off.set()

    monkeypatch.setattr(pg.PostgresWorker, "_power_off", power_off)
    await pg.PostgresQueue().enqueue(Job("test.pg_ok", {"name": "last"}))
    worker = pg.PostgresWorker(concurrency=1, stale_seconds=60, max_attempts=3, idle_shutdown_seconds=0.3)

    async with asyncio.timeout(10):
        await worker.run()
    assert powered_off.is_set()
    assert seen == [("last", 1)]


async def test_a_retry_in_backoff_keeps_the_worker_up(db, monkeypatch):
    async def power_off(self):
        raise AssertionError("powered off with a retry still queued")

    monkeypatch.setattr(pg.PostgresWorker, "_power_off", power_off)
    async with db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO background_jobs (id, kind, payload, status, attempts, run_after)
            VALUES ('later', 'test.pg_ok', :payload, 'queued', 1, now() + interval '1 hour')
        """), {"payload": json.dumps({"name": "later"})})
    worker = pg.PostgresWorker(concurrency=1, stale_seconds=60, max_attempts=3, idle_shutdown_seconds=0.1)
    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.6)
    worker.stop()
    await task


async def test_a_draining_worker_finishes_its_jobs_takes_no_new_ones_and_stops(db):
    await pg.PostgresQueue().enqueue(Job("test.pg_ok", {"name": "running"}))
    worker = pg.PostgresWorker(concurrency=1, stale_seconds=60, max_attempts=3)
    task = asyncio.create_task(worker.run())
    async with asyncio.timeout(5):
        while not worker._running:
            await asyncio.sleep(0.01)
    worker.drain()  # a deploy: the running job must finish, not be cut off
    await pg.PostgresQueue().enqueue(Job("test.pg_ok", {"name": "later"}))
    async with asyncio.timeout(5):
        await task
    assert worker.drained and [name for name, _ in seen] == ["running"]
    assert sorted(row.status for row in await _rows(db)) == ["done", "queued"]
