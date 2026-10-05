"""Background jobs: one interface, two backends.

``inprocess`` (the default) runs a job as a task in the API process, which is
how pipelines have always run. ``postgres`` (see ``jobs.postgres``) and
``sqs`` queue it for ``python -m jobs.worker`` processes, so the API can
restart, and workers can scale, without losing or duplicating runs.

A job is a ``kind`` plus a JSON-serialisable ``payload``; its handler is
registered with :func:`handler` and must be safe to run again after a crash
(SQS redelivers a message that was not deleted).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

Handler = Callable[["Job"], Awaitable[None]]

_handlers: dict[str, Handler] = {}


@dataclass(frozen=True)
class Job:
    kind: str
    payload: dict[str, Any]
    # How many times the queue has handed this job out; above 1 means an
    # earlier attempt died without finishing.
    attempt: int = field(default=1, compare=False)

    def to_message(self) -> str:
        return json.dumps({"kind": self.kind, "payload": self.payload})

    @classmethod
    def from_message(cls, body: str, attempt: int = 1) -> "Job":
        data = json.loads(body)
        return cls(kind=data["kind"], payload=data["payload"], attempt=attempt)


def handler(kind: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        _handlers[kind] = fn
        return fn
    return register


async def run_job(job: Job) -> None:
    fn = _handlers.get(job.kind)
    if fn is None:
        raise LookupError(f"No handler registered for job kind {job.kind!r}")
    await fn(job)


class JobQueue(Protocol):
    async def enqueue(self, job: Job) -> None: ...


class InProcessQueue:
    def __init__(self) -> None:
        # asyncio keeps only weak references to tasks; hold them until done.
        self._tasks: set[asyncio.Task] = set()

    async def enqueue(self, job: Job) -> None:
        task = asyncio.create_task(run_job(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


class SqsQueue:
    def __init__(self, queue_url: str, client: Any) -> None:
        self._queue_url = queue_url
        self._client = client

    async def enqueue(self, job: Job) -> None:
        await asyncio.to_thread(self._client.send_message, QueueUrl=self._queue_url, MessageBody=job.to_message())
        log.info("Job queued: kind=%s", job.kind)


def sqs_client() -> Any:
    import boto3

    settings = get_settings()
    kwargs: dict[str, Any] = {
        "region_name": settings.AWS_REGION,
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID or None,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY or None,
    }
    if settings.LOCALSTACK_ENDPOINT:
        kwargs["endpoint_url"] = settings.LOCALSTACK_ENDPOINT
    return boto3.client("sqs", **kwargs)


_queue: JobQueue | None = None


def uses_workers() -> bool:
    """True when jobs run in separate worker processes rather than in the API."""
    return get_settings().JOB_QUEUE_BACKEND in ("postgres", "sqs")


def get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        settings = get_settings()
        if settings.JOB_QUEUE_BACKEND == "postgres":
            from jobs.postgres import PostgresQueue

            _queue = PostgresQueue()
        elif uses_workers():
            if not settings.SQS_JOBS_QUEUE_URL:
                raise RuntimeError("JOB_QUEUE_BACKEND=sqs needs SQS_JOBS_QUEUE_URL")
            _queue = SqsQueue(settings.SQS_JOBS_QUEUE_URL, sqs_client())
        else:
            _queue = InProcessQueue()
    return _queue
