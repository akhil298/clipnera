import logging
import logging.config
import os
import re

from core.log_redaction import redact
from usage.context import current_scope

# Attributes the stdlib puts on every LogRecord. Anything outside this set was
# passed by the caller via extra={...} and is worth printing.
_STANDARD_RECORD_KEYS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"asctime", "message", "taskName"}

# Long values are truncated so one log line stays one line.
_MAX_VALUE_CHARS = 200


_NEWLINES = re.compile(r"\s*\n\s*")

# Libraries whose INFO/DEBUG output is noise in our logs; their warnings stay.
_QUIET_LOGGERS = (
    "sqlalchemy", "asyncpg", "httpx", "httpcore", "passlib", "botocore", "boto3", "s3transfer", "urllib3",
    "asyncio", "multipart", "python_multipart", "PIL", "numba", "matplotlib", "filelock", "fsspec",
    "huggingface_hub", "transformers", "speechbrain", "lightning", "lightning_fabric", "pytorch_lightning",
    "pyannote", "faster_whisper", "ctranslate2", "websockets", "watchfiles", "charset_normalizer",
)


class ContextFormatter(logging.Formatter):
    """One clean line per event: ``time level logger [project step] message | key=value``.

    The project and step come from the run scope (``usage.context``), so every
    line a pipeline writes says which video and stage it belongs to without each
    call passing them. A multi-line message is folded onto one line; only an
    exception's traceback keeps its own lines. ``extra={...}`` fields follow as
    ``key=value`` pairs.
    """

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        record = logging.makeLogRecord({**record.__dict__, "msg": _NEWLINES.sub(" ", message.strip()), "args": ()})
        tag = self._scope_tag(record)
        if tag:
            record.msg = f"{tag} {record.msg}"
        base = super().format(record)
        context = self._context(record)
        return redact(f"{base} | {context}" if context else base)

    @staticmethod
    def _scope_tag(record: logging.LogRecord) -> str:
        scope = current_scope()
        project = getattr(record, "project_id", None) or (scope.project_id if scope else None)
        if not project:
            return ""
        step = getattr(record, "step", None) or (scope.step if scope and scope.step != "unscoped" else None)
        return f"[{str(project)[:8]}{' ' + step if step else ''}]"

    @staticmethod
    def _context(record: logging.LogRecord) -> str:
        parts: list[str] = []
        for key, value in record.__dict__.items():
            # project_id and step are already in the [project step] tag;
            # color_message is uvicorn's ANSI-coloured copy of the message.
            if key in _STANDARD_RECORD_KEYS or key.startswith("_") or key in ("project_id", "step", "color_message"):
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
        ContextFormatter("%(asctime)s %(levelname)-7s %(name)-26s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    root_logger.addHandler(console_handler)
    # INFO unless LOG_LEVEL says otherwise; APP_DEBUG no longer turns servers to DEBUG.
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    for logger_name in _QUIET_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

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
