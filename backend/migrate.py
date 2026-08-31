from __future__ import annotations

import asyncio

from alembic import command
from alembic.config import Config

from core.config import get_settings


def _get_alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)
    return cfg


def run_migrations_sync() -> None:
    command.upgrade(_get_alembic_config(), "head")


async def run_migrations() -> None:
    await asyncio.to_thread(run_migrations_sync)
