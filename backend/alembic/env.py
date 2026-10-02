from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, ".")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from core.config import get_settings

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

from core.database import Base
from auth import model as auth_model
from clip import model as clip_model
from workspace import model as workspace_model
from pipeline import model as pipeline_model
from brand_kit import model as brand_kit_model
from subscription import model as subscription_model
from feature_flags import model as feature_flags_model
from social import model as social_model
from notifications import model as notifications_model
from usage import model as usage_model
from feedback import model as feedback_model
from broll import model as broll_model
from reels import model as reels_model
from edit_engine import model as edit_engine_model
from creator_intro import model as creator_intro_model
from editor import model as editor_model

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
    )

    def do_run_migrations(connection):
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    async def do_run_migrations_async():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    try:
        asyncio.get_running_loop()
        # Running inside an active event loop (e.g. FastAPI lifespan).
        # Use a worker thread to execute the async migration without
        # blocking the current loop.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, do_run_migrations_async)
            future.result()
    except RuntimeError:
        asyncio.run(do_run_migrations_async())


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
