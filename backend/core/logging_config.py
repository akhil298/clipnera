import logging
import logging.handlers
import sys
from pathlib import Path

from core.config import get_settings

settings = get_settings()

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logging() -> None:
    """Configure logging — show app logs, suppress verbose library logs."""
    log_level = logging.INFO

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "clipnera.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

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


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
