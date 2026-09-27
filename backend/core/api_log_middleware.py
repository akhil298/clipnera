import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging_config import get_logger

log = get_logger("api")


class APILogMiddleware(BaseHTTPMiddleware):
    """Logs one line per API request: method, path, status, duration, client IP.

    CORS preflights (OPTIONS) are skipped — they double the volume and carry no signal.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query}"
        client_ip = request.client.host if request.client else "unknown"

        log.info(f"{request.method} {path} {response.status_code} {duration_ms:.0f}ms {client_ip}")
        return response
