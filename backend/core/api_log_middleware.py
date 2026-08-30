import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging_config import get_logger

log = get_logger(__name__)


class APILogMiddleware(BaseHTTPMiddleware):
    """Logs every API request with method, path, status, duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        status = response.status_code

        log.info(f"{client_ip} | {method} {path} -> {status} ({duration_ms}ms)")

        return response
