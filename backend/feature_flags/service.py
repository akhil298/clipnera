"""Compatibility facade over the flag engine for the pre-revamp call sites.

Kept with the same methods so existing callers and tests work unchanged; new
code should call ``feature_flags.engine.flags`` with a ``FlagContext``. Removed
in phase 3 once every call site has moved.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from feature_flags.admin_service import AuditActor, FlagAdminService
from feature_flags.context import GLOBAL_CONTEXT, FlagContext
from feature_flags.engine import flags
from feature_flags.evaluation import Evaluator, build_snapshot
from feature_flags.model import FeatureFlag
from feature_flags.registry import FLAGS
from feature_flags.schema import AdminFeatureFlagListResponse


def resolve(stored: dict[str, bool]) -> dict[str, bool]:
    """Effective state of every declared flag for plain stored switches, with code defaults for the rest."""
    snapshot = build_snapshot(0, [{"key": key, "enabled": on} for key, on in stored.items()])
    evaluator = Evaluator(snapshot)
    return {key: bool(evaluator.flag(key).value) for key in FLAGS}


class FeatureFlagService:
    def __init__(self, session: AsyncSession, ctx: FlagContext = GLOBAL_CONTEXT) -> None:
        self._session = session
        self._ctx = ctx

    async def _evaluator(self) -> Evaluator:
        return Evaluator(await flags.snapshot_for(self._session), self._ctx)

    async def stored(self) -> dict[str, bool]:
        snapshot = await flags.snapshot_for(self._session)
        return {key: state.enabled for key, state in snapshot.flags.items()}

    async def effective(self) -> dict[str, bool]:
        evaluator = await self._evaluator()
        return {key: bool(evaluator.flag(key).value) for key in FLAGS}

    async def is_enabled(self, key: str) -> bool:
        if key not in FLAGS:
            raise KeyError(f"Undeclared feature flag {key!r}")
        return bool((await self._evaluator()).flag(key).value)

    async def require(self, *keys: str) -> None:
        """403 FEATURE_DISABLED unless every flag in ``keys`` is on."""
        flags.require(*keys, ctx=self._ctx, snapshot=await flags.snapshot_for(self._session))

    async def set(self, key: str, enabled: bool, admin_id: str) -> None:
        email = await self._session.scalar(select(User.email).where(User.id == admin_id))
        await FlagAdminService(self._session, AuditActor(admin_id, email)).legacy_switch(key, enabled)

    async def rows(self) -> dict[str, FeatureFlag]:
        result = await self._session.execute(select(FeatureFlag))
        return {row.key: row for row in result.scalars().all()}

    async def admin_list(self) -> AdminFeatureFlagListResponse:
        """The pre-revamp keys with their stored and effective state."""
        return await FlagAdminService(self._session).legacy_list()
