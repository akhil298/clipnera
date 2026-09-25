"""Pushes in-app notifications to a user's open dashboard streams (SSE).

In process memory, like the pipeline's progress store and the rate limiter:
the server runs a single uvicorn process. With several workers this would need
Redis pub/sub. Delivery is best effort; a client that misses an event catches
up from GET /notifications when it reconnects.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

QUEUE_SIZE = 50


class NotificationBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    @asynccontextmanager
    async def subscribe(self, user_id: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers.setdefault(user_id, set()).add(queue)
        try:
            yield queue
        finally:
            queues = self._subscribers.get(user_id)
            if queues is not None:
                queues.discard(queue)
                if not queues:
                    del self._subscribers[user_id]

    def publish(self, user_id: str, event: dict[str, Any]) -> None:
        for queue in self._subscribers.get(user_id, ()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # A stalled client; it resyncs from the list on reconnect.
                pass


broker = NotificationBroker()
