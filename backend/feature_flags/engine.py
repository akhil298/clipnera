"""The flag SDK: ``flags.is_enabled(key, ctx)``, ``flags.config(key, ctx)`` and friends.

Checks are synchronous and read an immutable in-process snapshot, so they cost
no queries. The snapshot is reloaded

- by the writing process right after an admin write commits,
- by every other process on ``NOTIFY flags_changed`` (one dedicated connection),
- and by a 15 s poll of ``flag_state.version`` as the safety net.

A failed reload keeps the last good snapshot; before the first load succeeds,
code defaults apply (release flags are off, so new UI fails closed).

Outside the API process's lifespan (tests, scripts, job workers) the engine is
not started; ``snapshot_for(session)`` then reads the state through the
caller's session, once per session.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from core.config import Environment, get_settings
from core.exceptions import CustomException
from core.logging_config import get_logger
from feature_flags.config_registry import CONFIGS, FLAGS_CLIENT_POLL_SECONDS, ConfigValue
from feature_flags.context import GLOBAL_CONTEXT, FlagContext
from feature_flags.evaluation import EMPTY_SNAPSHOT, Evaluation, Evaluator, Snapshot
from feature_flags.model import NOTIFY_CHANNEL
from feature_flags.registry import FLAGS
from feature_flags.repository import FlagRepository
from feature_flags.schema import FlagsBootstrapResponse

log = get_logger(__name__)

POLL_SECONDS = 15.0
_SESSION_SNAPSHOT = "feature_flags.snapshot"


class ForcedFlags:
    """Handle returned by ``flags.override()``; changes apply at once."""

    def __init__(self, engine: FlagEngine) -> None:
        self._engine = engine

    def set(self, key: str, on: bool) -> None:
        self._engine._force({key: on}, {})

    def set_config(self, key: str, value: ConfigValue) -> None:
        self._engine._force({}, {key: value})


class FlagEngine:
    def __init__(self) -> None:
        self._snapshot: Snapshot = EMPTY_SNAPSHOT
        self._checked_at = time.monotonic()
        self._forced_flags: dict[str, bool] = {}
        self._forced_config: dict[str, ConfigValue] = {}
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._db_engine: AsyncEngine | None = None
        self._listen_connection: AsyncConnection | None = None
        self._listen_driver: Any = None
        self._poll_task: asyncio.Task | None = None
        self._tasks: set[asyncio.Task] = set()
        self._lock: asyncio.Lock | None = None

    # -- reading -------------------------------------------------------------------------

    @property
    def started(self) -> bool:
        return self._session_factory is not None

    @property
    def snapshot(self) -> Snapshot:
        return self._view(self._snapshot)

    @property
    def snapshot_age_seconds(self) -> float:
        return time.monotonic() - self._checked_at

    @property
    def listening(self) -> bool:
        return self._listen_driver is not None and not self._listen_driver.is_closed()

    def evaluator(self, ctx: FlagContext = GLOBAL_CONTEXT, snapshot: Snapshot | None = None) -> Evaluator:
        return Evaluator(self.snapshot if snapshot is None else snapshot, ctx)

    def explain(self, key: str, ctx: FlagContext = GLOBAL_CONTEXT, snapshot: Snapshot | None = None) -> Evaluation:
        """The value of flag ``key`` for ``ctx``, with the reason, rule and bucket."""
        if key not in FLAGS:
            self._unknown(key)
            return Evaluation(key, False, "DEFAULT")
        return self.evaluator(ctx, snapshot).flag(key)

    def is_enabled(self, key: str, ctx: FlagContext = GLOBAL_CONTEXT, snapshot: Snapshot | None = None) -> bool:
        return bool(self.explain(key, ctx, snapshot).value)

    def require(self, *keys: str, ctx: FlagContext = GLOBAL_CONTEXT, snapshot: Snapshot | None = None) -> None:
        """403 FEATURE_DISABLED unless every flag in ``keys`` is on (the body clients already handle)."""
        evaluator = self.evaluator(ctx, snapshot)
        for key in keys:
            if not evaluator.flag(key).value:
                raise CustomException(
                    message=f"{FLAGS[key].label} is not available right now.",
                    code="FEATURE_DISABLED",
                    status_code=403,
                    extra={"feature": key},
                )

    def explain_config(
        self, key: str, ctx: FlagContext = GLOBAL_CONTEXT, snapshot: Snapshot | None = None
    ) -> Evaluation:
        return self.evaluator(ctx, snapshot).config(key)

    def config(self, key: str, ctx: FlagContext = GLOBAL_CONTEXT, snapshot: Snapshot | None = None) -> ConfigValue:
        return self.explain_config(key, ctx, snapshot).value

    def bootstrap(
        self, ctx: FlagContext, subject: Literal["user", "anonymous"], snapshot: Snapshot | None = None
    ) -> FlagsBootstrapResponse:
        """Every client flag and value for ``ctx``; only public ones for anonymous visitors.
        Never descriptions, owners, rules, overrides or server-only keys."""
        snapshot = self.snapshot if snapshot is None else snapshot
        evaluator = self.evaluator(ctx, snapshot)
        anonymous = subject == "anonymous"
        return FlagsBootstrapResponse(
            version=snapshot.version,
            evaluated_at=datetime.now(timezone.utc),
            subject=subject,
            flags={
                key: bool(evaluator.flag(key).value)
                for key, flag in FLAGS.items()
                if flag.client and (flag.public or not anonymous)
            },
            config={
                key: evaluator.config(key).value
                for key, config in CONFIGS.items()
                if config.client and (config.public or not anonymous)
            },
            poll_seconds=int(evaluator.config(FLAGS_CLIENT_POLL_SECONDS).value),
        )

    async def snapshot_for(self, session: AsyncSession) -> Snapshot:
        """The engine's snapshot when started; otherwise the state read through ``session``,
        once per session (inside a savepoint, so a failure cannot spoil the caller's transaction)."""
        if self.started:
            return self.snapshot
        cached = session.info.get(_SESSION_SNAPSHOT)
        if cached is None:
            try:
                async with session.begin_nested():
                    cached = await FlagRepository(session).load_snapshot()
            except Exception as exc:
                log.warning(f"Could not read feature flags ({type(exc).__name__}); using the last good state")
                cached = self._snapshot
            session.info[_SESSION_SNAPSHOT] = cached
        return self._view(cached)

    # -- lifecycle -----------------------------------------------------------------------

    async def start(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        db_engine: AsyncEngine | None = None,
        poll_seconds: float = POLL_SECONDS,
    ) -> None:
        """Load the snapshot, LISTEN for changes and poll as a fallback. Never raises."""
        if self.started:
            return
        if session_factory is None or db_engine is None:
            from core.database import AsyncSessionLocal, engine

            session_factory, db_engine = session_factory or AsyncSessionLocal, db_engine or engine
        self._session_factory, self._db_engine = session_factory, db_engine
        self._lock = asyncio.Lock()
        await self.refresh()
        await self._listen()
        self._poll_task = asyncio.create_task(self._poll(poll_seconds))

    async def stop(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            await asyncio.gather(self._poll_task, return_exceptions=True)
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._unlisten()
        self._poll_task = self._session_factory = self._db_engine = self._lock = None

    async def refresh(self) -> bool:
        """Reload from the database. Keeps the last good snapshot on failure."""
        if self._session_factory is None or self._lock is None:
            return False
        async with self._lock:
            try:
                async with self._session_factory() as session:
                    self._snapshot = await FlagRepository(session).load_snapshot()
            except Exception as exc:
                log.error(f"Feature flag refresh failed ({type(exc).__name__}); keeping version "
                          f"{self._snapshot.version}")
                return False
            self._checked_at = time.monotonic()
            return True

    async def after_write(self, session: AsyncSession) -> None:
        """Called after an admin write commits: this process sees it at once."""
        session.info.pop(_SESSION_SNAPSHOT, None)
        await self.refresh()

    async def _poll(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                if not self.listening:
                    await self._listen()
                async with self._session_factory() as session:
                    version = await FlagRepository(session).state_version()
                if version != self._snapshot.version:
                    await self.refresh()
                else:
                    self._checked_at = time.monotonic()
            except Exception as exc:
                log.warning(f"Feature flag poll failed ({type(exc).__name__})")

    async def _listen(self) -> None:
        await self._unlisten()
        try:
            connection = await self._db_engine.connect()
            raw = await connection.get_raw_connection()
            await raw.driver_connection.add_listener(NOTIFY_CHANNEL, self._on_notify)
        except Exception as exc:
            log.warning(f"LISTEN {NOTIFY_CHANNEL} failed ({type(exc).__name__}); polling only")
            return
        self._listen_connection, self._listen_driver = connection, raw.driver_connection

    async def _unlisten(self) -> None:
        connection, driver = self._listen_connection, self._listen_driver
        self._listen_connection = self._listen_driver = None
        if connection is None:
            return
        try:
            if not driver.is_closed():
                await driver.remove_listener(NOTIFY_CHANNEL, self._on_notify)
            await connection.close()
        except Exception as exc:
            log.warning(f"Closing the flag listener failed ({type(exc).__name__})")

    def _on_notify(self, _connection: Any, _pid: int, _channel: str, payload: str) -> None:
        if payload.isdigit() and int(payload) == self._snapshot.version:
            return
        task = asyncio.get_running_loop().create_task(self.refresh())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # -- forcing (tests and development) -------------------------------------------------

    @contextmanager
    def override(
        self, flags: Mapping[str, bool] | None = None, config: Mapping[str, ConfigValue] | None = None
    ) -> Iterator[ForcedFlags]:
        """Force values for everyone inside the block. Hierarchy still applies. Refused in production."""
        if get_settings().ENVIRONMENT == Environment.PRODUCTION:
            raise RuntimeError("Flags cannot be forced in production; use a per-user override")
        saved = dict(self._forced_flags), dict(self._forced_config)
        try:
            self._force(flags or {}, config or {})
            yield ForcedFlags(self)
        finally:
            self._forced_flags, self._forced_config = saved

    def _force(self, flags: Mapping[str, bool], config: Mapping[str, ConfigValue]) -> None:
        for key in flags:
            if key not in FLAGS:
                raise KeyError(f"Undeclared feature flag {key!r}")
        validated = {key: CONFIGS[key].validate(value) for key, value in config.items()}
        self._forced_flags.update(flags)
        self._forced_config.update(validated)

    def _view(self, snapshot: Snapshot) -> Snapshot:
        if not (self._forced_flags or self._forced_config):
            return snapshot
        return snapshot.with_forced(self._forced_flags, self._forced_config)

    @staticmethod
    def _unknown(key: str) -> None:
        if get_settings().ENVIRONMENT != Environment.PRODUCTION:
            raise KeyError(f"Undeclared feature flag {key!r}")
        log.error(f"Undeclared feature flag {key!r} read as off")


flags = FlagEngine()
