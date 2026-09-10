import logging
import logging.config


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
        logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    )
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)

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


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
