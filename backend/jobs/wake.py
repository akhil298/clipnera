"""Wake the job worker's EC2 machine while jobs are waiting.

The worker powers its machine off once the queue has been empty for
``WORKER_IDLE_SHUTDOWN_SECONDS`` (see ``jobs.postgres``). The API starts it
again right after queuing a job, and every ``CHECK_SECONDS`` while any job is
still queued: EC2 refuses to start a machine that is still shutting down, so
a job queued in that moment is picked up by the next check.

The EC2 client uses the machine's IAM role, which needs ec2:StartInstances on
the worker instance; settings' access keys are for S3 only.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text

from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger

log = get_logger(__name__)

CHECK_SECONDS = 30

_PENDING = text("SELECT EXISTS (SELECT 1 FROM background_jobs WHERE status = ANY(:statuses))")

_ec2: Any = None


async def has_pending_jobs(include_running: bool = True) -> bool:
    """Whether any job is queued (or, by default, running) -- including retries in backoff."""
    statuses = ["queued", "running"] if include_running else ["queued"]
    async with AsyncSessionLocal() as session:
        return bool((await session.execute(_PENDING, {"statuses": statuses})).scalar())


def _client() -> Any:
    global _ec2
    if _ec2 is None:
        import boto3

        _ec2 = boto3.client("ec2", region_name=get_settings().AWS_REGION)
    return _ec2


async def wake_worker() -> None:
    """Start the worker machine; a no-op when it is running or not configured."""
    instance_id = get_settings().WORKER_INSTANCE_ID
    if not instance_id:
        return
    try:
        await asyncio.to_thread(_client().start_instances, InstanceIds=[instance_id])
    except Exception as exc:
        # Usually IncorrectInstanceState while it shuts down; the next check retries.
        log.info("Worker machine not started yet: %s", exc)


async def _keep_awake() -> None:
    while True:
        await asyncio.sleep(CHECK_SECONDS)
        try:
            if await has_pending_jobs():
                await wake_worker()
        except Exception:
            log.exception("Worker wake check failed")


@asynccontextmanager
async def waking_worker() -> AsyncIterator[None]:
    """Run the wake check for the lifetime of the API when a worker machine is set."""
    if not get_settings().WORKER_INSTANCE_ID:
        yield
        return
    task = asyncio.create_task(_keep_awake())
    try:
        yield
    finally:
        task.cancel()
