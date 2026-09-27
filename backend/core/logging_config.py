import logging
import logging.config
import os

from core.log_redaction import redact

# Attributes the stdlib puts on every LogRecord. Anything outside this set was
# passed by the caller via extra={...} and is worth printing.
_STANDARD_RECORD_KEYS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"asctime", "message", "taskName"}

# Long values are truncated so one log line stays one line.
_MAX_VALUE_CHARS = 200


class ContextFormatter(logging.Formatter):
    """Renders ``extra={...}`` fields after the message as ``key=value`` pairs.

    The previous formatter dropped them silently, so the structured context
    attached throughout the pipeline never reached the log output and every line
    read as a bare status string.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        context = self._context(record)
        return redact(f"{base} | {context}" if context else base)

    @staticmethod
    def _context(record: logging.LogRecord) -> str:
        parts: list[str] = []
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_KEYS or key.startswith("_"):
                continue
            text = str(value)
            if len(text) > _MAX_VALUE_CHARS:
                text = f"{text[:_MAX_VALUE_CHARS]}...({len(text)} chars)"
            if any(c in text for c in " \t="):
                text = f'"{text}"'
            parts.append(f"{key}={text}")
        return " ".join(parts)


def setup_logging() -> None:
    """Configure logging — show app logs, suppress verbose library logs."""
    root_logger = logging.getLogger()
    if getattr(root_logger, "_clipnera_configured", False):
        return
    root_logger._clipnera_configured = True

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        ContextFormatter("%(asctime)s %(levelname)-8s %(name)-28s %(message)s")
    )
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG if os.getenv("APP_DEBUG", "").lower() in ("1", "true") else logging.INFO)

    for logger_name in [
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "asyncpg",
        "httpx",
        "httpcore",
        "passlib",
        "botocore",
        "boto3",
        "urllib3",
    ]:
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    for uvicorn_logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(logging.INFO)
        for handler in list(uvicorn_logger.handlers):
            uvicorn_logger.removeHandler(handler)

    # APILogMiddleware already writes one line per request; uvicorn's access log would duplicate it.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
