import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging_config import get_logger

log = get_logger("api")

# Endpoints the frontend polls every few seconds; a successful poll is DEBUG so
# the log shows what users did, not the page refreshing its progress bars.
POLLING_PREFIXES = (
    "/health",
    "/api/v1/pipeline/status",
    "/api/v1/pipeline/progress",
    "/api/v1/clips/progress/",
    "/api/v1/notifications",
    "/api/v1/subscription/entitlements",
)


def _level(path: str, status: int) -> int:
    if status >= 500:
        return logging.WARNING
    if status < 400 and path.startswith(POLLING_PREFIXES):
        return logging.DEBUG
    return logging.INFO


class APILogMiddleware(BaseHTTPMiddleware):
    """Logs one line per API request: method, path, status, duration, client IP.

    CORS preflights (OPTIONS) are skipped — they double the volume and carry no
    signal — and successful polls are DEBUG (see POLLING_PREFIXES).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        path = request.url.path
        level = _level(path, response.status_code)
        if not log.isEnabledFor(level):
            return response
        if request.url.query:
            path = f"{path}?{request.url.query}"
        client_ip = request.client.host if request.client else "unknown"

        log.log(level, f"{request.method} {path} {response.status_code} {duration_ms:.0f}ms {client_ip}")
        return response
