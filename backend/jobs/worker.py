"""Job worker: ``python -m jobs.worker``.

Runs jobs from the queue JOB_QUEUE_BACKEND names: Postgres (``jobs.postgres``)
or SQS. For SQS it long-polls the jobs queue, runs up to ``JOB_WORKER_CONCURRENCY`` jobs at once,
and deletes a message only after its handler returns. While a job runs, its
message's visibility is extended on a heartbeat, so a pipeline that takes an
hour is not handed to a second worker; if this process dies, the heartbeat
stops and SQS redelivers the job (after too many attempts the queue's
redrive policy moves it to the dead-letter queue).
"""

from __future__ import annotations

import asyncio
import signal
from typing import Any

from core.config import get_settings
from core.logging_config import get_logger
from jobs.queue import Job, run_job, sqs_client

log = get_logger(__name__)


class Worker:
    def __init__(
        self, client: Any, queue_url: str, concurrency: int, visibility_timeout: int, wait_seconds: int = 20,
    ) -> None:
        self._client = client
        self._queue_url = queue_url
        self._concurrency = concurrency
        self._visibility = visibility_timeout
        self._wait = wait_seconds
        self._stopping = asyncio.Event()
        self._running: set[asyncio.Task] = set()

    def stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        log.info("Worker started: queue=%s", self._queue_url)
        while not self._stopping.is_set():
            await self.poll_once()
        if self._running:
            log.info("Worker stopping; %d job(s) will be redelivered and resumed", len(self._running))
            for task in self._running:
                task.cancel()
            await asyncio.gather(*self._running, return_exceptions=True)

    async def poll_once(self) -> None:
        free = self._concurrency - len(self._running)
        if free <= 0:
            await asyncio.wait(self._running, return_when=asyncio.FIRST_COMPLETED)
            return
        response = await asyncio.to_thread(
            self._client.receive_message,
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=min(10, free),
            WaitTimeSeconds=self._wait,
            VisibilityTimeout=self._visibility,
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in response.get("Messages", []):
            task = asyncio.create_task(self._handle(message))
            self._running.add(task)
            task.add_done_callback(self._running.discard)

    async def _handle(self, message: dict) -> None:
        receipt = message["ReceiptHandle"]
        heartbeat = asyncio.create_task(self._heartbeat(receipt))
        try:
            attempt = int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
            job = Job.from_message(message["Body"], attempt=attempt)
            log.info("Job started: kind=%s attempt=%d", job.kind, attempt)
            await run_job(job)
            await asyncio.to_thread(self._client.delete_message, QueueUrl=self._queue_url, ReceiptHandle=receipt)
            log.info("Job done: kind=%s", job.kind)
        except asyncio.CancelledError:
            # Shutting down: leave the message so another worker picks it up.
            raise
        except Exception:
            log.exception("Job failed; it will be retried after the visibility timeout")
        finally:
            heartbeat.cancel()

    async def _heartbeat(self, receipt: str) -> None:
        while True:
            await asyncio.sleep(self._visibility / 3)
            try:
                await asyncio.to_thread(
                    self._client.change_message_visibility,
                    QueueUrl=self._queue_url, ReceiptHandle=receipt, VisibilityTimeout=self._visibility,
                )
            except Exception as exc:
                log.warning("Could not extend job visibility: %s", exc)


def load_handlers() -> None:
    """Import every module that registers a job handler."""
    import broll.generation_job  # noqa: F401
    import broll.service  # noqa: F401
    import pipeline.service  # noqa: F401
    import reels.jobs  # noqa: F401
    import creator_intro.jobs  # noqa: F401
    import edit_engine.jobs  # noqa: F401


def _worker() -> Any:
    settings = get_settings()
    if settings.JOB_QUEUE_BACKEND == "postgres":
        from jobs.postgres import worker_from_settings

        return worker_from_settings()
    if settings.JOB_QUEUE_BACKEND != "sqs":
        raise SystemExit("JOB_QUEUE_BACKEND is 'inprocess': jobs run in the API, so no worker is needed")
    if not settings.SQS_JOBS_QUEUE_URL:
        raise SystemExit("SQS_JOBS_QUEUE_URL is not set")
    return Worker(
        sqs_client(), settings.SQS_JOBS_QUEUE_URL,
        settings.JOB_WORKER_CONCURRENCY, settings.JOB_VISIBILITY_TIMEOUT_SECONDS,
    )


async def main() -> None:
    load_handlers()
    worker = _worker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
