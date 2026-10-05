from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from feature_flags.evaluation import Snapshot, build_snapshot
from feature_flags.model import (
    NOTIFY_CHANNEL,
    STATE_ROW_ID,
    AdminPermission,
    FeatureFlag,
    FlagAuditLog,
    FlagSegment,
    FlagStateVersion,
    RemoteConfig,
    TargetingOverride,
)
from workspace.model import Workspace


class FlagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- snapshot ------------------------------------------------------------------------

    async def state_version(self) -> int:
        version = await self._session.scalar(
            select(FlagStateVersion.version).where(FlagStateVersion.id == STATE_ROW_ID)
        )
        return int(version or 0)

    async def load_snapshot(self) -> Snapshot:
        """Every stored row the engine needs: a few small tables, read in one go."""
        version = await self.state_version()
        now = datetime.utcnow()
        return build_snapshot(
            version,
            await self._rows(select(FeatureFlag.__table__)),
            await self._rows(select(RemoteConfig.__table__)),
            await self._rows(select(FlagSegment.__table__)),
            await self._rows(
                select(TargetingOverride.__table__).where(
                    or_(TargetingOverride.expires_at.is_(None), TargetingOverride.expires_at > now)
                )
            ),
        )

    async def _rows(self, statement) -> list[dict[str, Any]]:
        return [dict(row) for row in (await self._session.execute(statement)).mappings().all()]

    # -- writes --------------------------------------------------------------------------

    async def bump_version(self) -> int:
        """Bump the shared version and NOTIFY other processes; both take effect on commit."""
        statement = pg_insert(FlagStateVersion).values(id=STATE_ROW_ID, version=1)
        statement = statement.on_conflict_do_update(
            index_elements=[FlagStateVersion.id], set_={"version": FlagStateVersion.version + 1}
        ).returning(FlagStateVersion.version)
        version = int((await self._session.execute(statement)).scalar_one())
        await self._session.execute(
            text("SELECT pg_notify(:channel, :payload)"), {"channel": NOTIFY_CHANNEL, "payload": str(version)}
        )
        return version

    def audit(self, **entry: Any) -> None:
        self._session.add(FlagAuditLog(**entry))

    # -- reads ---------------------------------------------------------------------------

    async def flag(self, key: str, lock: bool = False) -> FeatureFlag | None:
        return await self._get(select(FeatureFlag).where(FeatureFlag.key == key), lock)

    async def flags(self) -> dict[str, FeatureFlag]:
        return {row.key: row for row in (await self._session.scalars(select(FeatureFlag))).all()}

    async def config(self, key: str, lock: bool = False) -> RemoteConfig | None:
        return await self._get(select(RemoteConfig).where(RemoteConfig.key == key), lock)

    async def configs(self) -> dict[str, RemoteConfig]:
        return {row.key: row for row in (await self._session.scalars(select(RemoteConfig))).all()}

    async def segment(self, key: str, lock: bool = False) -> FlagSegment | None:
        return await self._get(select(FlagSegment).where(FlagSegment.key == key), lock)

    async def segments(self) -> list[FlagSegment]:
        return list((await self._session.scalars(select(FlagSegment).order_by(FlagSegment.key))).all())

    async def segment_keys(self) -> set[str]:
        return set((await self._session.scalars(select(FlagSegment.key))).all())

    async def override(self, kind: str, key: str, subject_type: str, subject_id: str) -> TargetingOverride | None:
        return await self._session.get(TargetingOverride, (kind, key, subject_type, subject_id))

    async def overrides(self, kind: str, key: str) -> list[TargetingOverride]:
        statement = (
            select(TargetingOverride)
            .where(TargetingOverride.target_kind == kind, TargetingOverride.target_key == key)
            .order_by(TargetingOverride.created_at)
        )
        return list((await self._session.scalars(statement)).all())

    async def override_counts(self, kind: str) -> dict[str, int]:
        statement = (
            select(TargetingOverride.target_key, func.count())
            .where(TargetingOverride.target_kind == kind)
            .group_by(TargetingOverride.target_key)
        )
        return {key: count for key, count in (await self._session.execute(statement)).all()}

    async def audit_page(self, target_key: str | None, before_id: int | None, limit: int) -> list[FlagAuditLog]:
        statement = select(FlagAuditLog).order_by(FlagAuditLog.id.desc()).limit(limit)
        if target_key is not None:
            statement = statement.where(FlagAuditLog.target_key == target_key)
        if before_id is not None:
            statement = statement.where(FlagAuditLog.id < before_id)
        return list((await self._session.scalars(statement)).all())

    async def find_user(self, ref: str) -> User | None:
        """A user by id or email."""
        statement = select(User).where(or_(User.id == ref, func.lower(User.email) == ref.strip().lower()))
        return (await self._session.scalars(statement.limit(1))).first()

    async def emails(self, user_ids: set[str | None]) -> dict[str, str]:
        ids = {user_id for user_id in user_ids if user_id}
        if not ids:
            return {}
        rows = await self._session.execute(select(User.id, User.email).where(User.id.in_(ids)))
        return {user_id: email for user_id, email in rows.all()}

    async def workspace_names(self, workspace_ids: set[str]) -> dict[str, str]:
        if not workspace_ids:
            return {}
        rows = await self._session.execute(
            select(Workspace.id, Workspace.name).where(Workspace.id.in_(workspace_ids))
        )
        return {workspace_id: name for workspace_id, name in rows.all()}

    async def permissions(self, user_id: str) -> set[str]:
        statement = select(AdminPermission.permission).where(AdminPermission.user_id == user_id)
        return set((await self._session.scalars(statement)).all())

    async def _get(self, statement, lock: bool):
        if lock:
            statement = statement.with_for_update()
        return (await self._session.scalars(statement)).first()
