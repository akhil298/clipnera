"""Admin reads and audited writes for flags, remote config and segments.

Every write lands in one transaction with its audit row and a bump of the shared
version (which NOTIFYs other processes), then refreshes this process's snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import UserRole
from core.exceptions import CustomException
from feature_flags.config_registry import CONFIGS, ConfigDefinition, ConfigValueError
from feature_flags.context import GLOBAL_CONTEXT, FlagContext, load_context
from feature_flags.engine import flags
from feature_flags.evaluation import Evaluator
from feature_flags.model import FeatureFlag, FlagSegment, RemoteConfig, TargetingOverride
from feature_flags.registry import FLAGS, LEGACY_KEYS, FlagDefinition, children, dependants
from feature_flags.repository import FlagRepository
from feature_flags.schema import (
    AdminAuditEntry,
    AdminAuditPageResponse,
    AdminConfigDetailResponse,
    AdminConfigListResponse,
    AdminConfigSummary,
    AdminConfigUpdateRequest,
    AdminEvaluateRequest,
    AdminEvaluationResponse,
    AdminFeatureFlagListResponse,
    AdminFeatureFlagResponse,
    AdminFlagDetailResponse,
    AdminFlagKillRequest,
    AdminFlagListResponse,
    AdminFlagSummary,
    AdminFlagUpdateRequest,
    AdminOverrideRequest,
    AdminSegmentListResponse,
    AdminSegmentResponse,
    AdminSegmentUpdateRequest,
    ConfigRule,
    FlagRule,
    OverrideResponse,
)
from subscription.model import PlanSlug

LEGACY_REASON = "Legacy switch (no reason)"
STALE_AFTER_FULL_ROLLOUT = timedelta(days=14)
AUDIT_PAGE_SIZE = 50
MAX_OVERRIDES = 500
PLANS = tuple(plan.value for plan in PlanSlug)
ROLES = tuple(role.value for role in UserRole)


@dataclass(frozen=True)
class AuditActor:
    id: str | None
    email: str | None
    request_id: str | None = None
    ip: str | None = None


def _invalid(message: str, field: str, code: str = "VALIDATION_FAILED") -> CustomException:
    return CustomException(message=message, code=code, status_code=422, extra={"field": field})


def _not_found(what: str) -> CustomException:
    return CustomException(message=f"Unknown {what}", code="NOT_FOUND", status_code=404)


def _check_version(current: int, expected: int) -> None:
    if current != expected:
        raise CustomException(
            message="Someone changed this while you were editing.",
            code="FLAG_VERSION_CONFLICT",
            status_code=409,
            extra={"version": current},
        )


def _flag_definition(key: str) -> FlagDefinition:
    if key not in FLAGS:
        raise _not_found("feature flag")
    return FLAGS[key]


def _config_definition(key: str) -> ConfigDefinition:
    if key not in CONFIGS:
        raise _not_found("config key")
    return CONFIGS[key]


def _flag_state(row: FeatureFlag | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "enabled": row.enabled, "rollout_bps": row.rollout_bps, "rules": row.rules, "bucket_salt": row.bucket_salt,
        "killed": row.killed, "killed_reason": row.killed_reason, "version": row.version,
    }


def _config_state(row: RemoteConfig | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"default_value": row.default_value, "rules": row.rules, "version": row.version}


def _override_state(row: TargetingOverride | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "value": row.value, "reason": row.reason,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


def _segment_state(row: FlagSegment) -> dict[str, Any]:
    return {
        "user_ids": sorted(row.user_ids), "email_domains": sorted(row.email_domains), "roles": sorted(row.roles),
        "version": row.version,
    }


def _naive_utc(value: datetime | None) -> datetime | None:
    """Stored timestamps are naive UTC, like the rest of the schema."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class FlagAdminService:
    def __init__(self, session: AsyncSession, actor: AuditActor | None = None) -> None:
        self._session = session
        self._repo = FlagRepository(session)
        self._actor = actor

    # -- flags: reads --------------------------------------------------------------------

    async def list_flags(self) -> AdminFlagListResponse:
        rows = await self._repo.flags()
        counts = await self._repo.override_counts("flag")
        emails = await self._repo.emails({row.updated_by for row in rows.values()})
        snapshot = await flags.snapshot_for(self._session)
        evaluator = Evaluator(snapshot)
        return AdminFlagListResponse(
            flags=[
                AdminFlagSummary(**self._flag_summary(definition, rows.get(key), counts, emails, evaluator))
                for key, definition in FLAGS.items()
            ],
            snapshot_version=snapshot.version,
        )

    async def get_flag(self, key: str) -> AdminFlagDetailResponse:
        definition = _flag_definition(key)
        row = await self._repo.flag(key)
        overrides = await self._repo.overrides("flag", key)
        emails = await self._repo.emails(
            {row.updated_by if row else None, row.killed_by if row else None}
            | {override.created_by for override in overrides}
        )
        summary = self._flag_summary(
            definition, row, {key: len(overrides)}, emails, Evaluator(await flags.snapshot_for(self._session))
        )
        return AdminFlagDetailResponse(
            **summary,
            rules=[FlagRule.model_validate(rule) for rule in (row.rules if row else [])],
            overrides=await self._override_responses(overrides, emails),
            children=children(key),
            dependants=dependants(key),
            killed_reason=row.killed_reason if row and row.killed else None,
            killed_at=row.killed_at if row and row.killed else None,
            killed_by_email=emails.get(row.killed_by) if row and row.killed and row.killed_by else None,
        )

    def _flag_summary(
        self,
        definition: FlagDefinition,
        row: FeatureFlag | None,
        counts: dict[str, int],
        emails: dict[str, str],
        evaluator: Evaluator,
    ) -> dict[str, Any]:
        return {
            "key": definition.key, "label": definition.label, "description": definition.description,
            "owner": definition.owner, "kind": definition.kind, "parent": definition.parent,
            "requires": list(definition.requires), "default": definition.default, "client": definition.client,
            "public": definition.public, "live_update": definition.live_update, "created": definition.created,
            "expires": definition.expires, "stale": self._stale(definition, row),
            "enabled": bool(row and row.enabled), "killed": bool(row and row.killed),
            "rollout_bps": row.rollout_bps if row else 10000,
            "rule_count": len(row.rules) if row else 0,
            "override_count": counts.get(definition.key, 0),
            "blocked_by": evaluator.flag(definition.key).blocked_by,
            "version": row.version if row else 0,
            "updated_at": row.updated_at if row else None,
            "updated_by_email": emails.get(row.updated_by) if row and row.updated_by else None,
        }

    @staticmethod
    def _stale(definition: FlagDefinition, row: FeatureFlag | None) -> bool:
        if definition.expires is not None and date.today() > definition.expires:
            return True
        return (
            definition.kind == "release"
            and row is not None
            and row.enabled
            and not row.killed
            and row.rollout_bps >= 10000
            and all(rule.get("serve") for rule in row.rules)
            and datetime.utcnow() - row.updated_at > STALE_AFTER_FULL_ROLLOUT
        )

    async def evaluate(self, key: str, body: AdminEvaluateRequest) -> AdminEvaluationResponse:
        _flag_definition(key)
        ctx = FlagContext(workspace_id=body.workspace_id)
        if body.user:
            user = await self._repo.find_user(body.user)
            if user is None:
                raise _not_found("user")
            ctx = await load_context(self._session, FlagContext(user_id=user.id, workspace_id=body.workspace_id))
        result = flags.explain(key, ctx, await flags.snapshot_for(self._session))
        return AdminEvaluationResponse(
            key=key, value=result.value, reason=result.reason, rule_id=result.rule_id,
            blocked_by=result.blocked_by, bucket=result.bucket,
        )

    # -- flags: writes -------------------------------------------------------------------

    async def update_flag(self, key: str, body: AdminFlagUpdateRequest) -> AdminFlagDetailResponse:
        _flag_definition(key)
        await self._validate_rules(body.rules)
        row = await self._repo.flag(key, lock=True)
        _check_version(row.version if row else 0, body.expected_version)
        before = _flag_state(row)
        row = row or self._new_flag_row(key)
        row.enabled = body.enabled
        row.rules = [rule.model_dump() for rule in body.rules]
        row.rollout_bps = body.rollout_bps
        await self._save_flag(row, before, "flag.update", body.reason)
        return await self.get_flag(key)

    async def kill(self, key: str, body: AdminFlagKillRequest) -> AdminFlagDetailResponse:
        definition = _flag_definition(key)
        if body.confirm_key != key:
            raise _invalid("Type the flag key to confirm.", "confirm_key")
        row = await self._repo.flag(key, lock=True)
        if row is None or not row.killed:
            before = _flag_state(row)
            # A kill never touches targeting, so a restore returns exactly to it.
            row = row or self._new_flag_row(key, enabled=definition.default)
            row.killed, row.killed_reason = True, body.reason
            row.killed_by, row.killed_at = self._actor_id, datetime.utcnow()
            await self._save_flag(row, before, "flag.kill", body.reason)
        return await self.get_flag(key)

    async def unkill(self, key: str, reason: str) -> AdminFlagDetailResponse:
        _flag_definition(key)
        row = await self._repo.flag(key, lock=True)
        if row is not None and row.killed:
            before = _flag_state(row)
            row.killed, row.killed_reason, row.killed_by, row.killed_at = False, None, None, None
            await self._save_flag(row, before, "flag.unkill", reason)
        return await self.get_flag(key)

    async def legacy_switch(self, key: str, enabled: bool) -> None:
        """PATCH /admin/features/{key}: the pre-revamp switch, now audited."""
        if key not in LEGACY_KEYS:
            raise _not_found("feature flag")
        row = await self._repo.flag(key, lock=True)
        before = _flag_state(row)
        row = row or self._new_flag_row(key)
        row.enabled = enabled
        await self._save_flag(row, before, "legacy.switch", LEGACY_REASON)

    def _new_flag_row(self, key: str, enabled: bool = False) -> FeatureFlag:
        row = FeatureFlag(key=key, enabled=enabled, rollout_bps=10000, rules=[], killed=False, version=0)
        self._session.add(row)
        return row

    async def _save_flag(self, row: FeatureFlag, before: dict[str, Any] | None, action: str, reason: str) -> None:
        row.version += 1
        row.updated_by, row.updated_at = self._actor_id, datetime.utcnow()
        await self._commit(action, "flag", row.key, before, _flag_state(row), reason)

    # -- overrides (flags and config) ----------------------------------------------------

    async def set_override(self, kind: str, key: str, body: AdminOverrideRequest) -> None:
        value = self._override_value(kind, key, body.value)
        subject_id = await self._resolve_subject(body.subject_type, body.subject)
        row = await self._repo.override(kind, key, body.subject_type, subject_id)
        if row is None and len(await self._repo.overrides(kind, key)) >= MAX_OVERRIDES:
            raise _invalid(f"At most {MAX_OVERRIDES} overrides per key; use a segment instead.", "subject")
        before = _override_state(row)
        if row is None:
            row = TargetingOverride(
                target_kind=kind, target_key=key, subject_type=body.subject_type, subject_id=subject_id,
            )
            self._session.add(row)
        row.value, row.reason, row.expires_at = value, body.reason, _naive_utc(body.expires_at)
        row.created_by, row.created_at = self._actor_id, datetime.utcnow()
        await self._commit("override.set", kind, key, before, _override_state(row), body.reason,
                           body.subject_type, subject_id)

    async def delete_override(self, kind: str, key: str, subject_type: str, subject_id: str, reason: str) -> None:
        self._definition(kind, key)
        row = await self._repo.override(kind, key, subject_type, subject_id)
        if row is None:
            raise _not_found("override")
        before = _override_state(row)
        await self._session.delete(row)
        await self._commit("override.delete", kind, key, before, None, reason, subject_type, subject_id)

    def _definition(self, kind: str, key: str) -> FlagDefinition | ConfigDefinition:
        return _flag_definition(key) if kind == "flag" else _config_definition(key)

    def _override_value(self, kind: str, key: str, value: Any) -> Any:
        definition = self._definition(kind, key)
        if isinstance(definition, FlagDefinition):
            if not isinstance(value, bool):
                raise _invalid("A flag override is on or off.", "value")
            return value
        if definition.targeting == "global":
            raise _invalid(f"{key} is global and takes no overrides.", "value", "CONFIG_INVALID")
        return self._config_value(definition, value, "value")

    async def _resolve_subject(self, subject_type: str, subject: str) -> str:
        if subject_type == "user":
            user = await self._repo.find_user(subject)
            if user is None:
                raise _not_found("user")
            return user.id
        if subject not in await self._repo.workspace_names({subject}):
            raise _not_found("workspace")
        return subject

    async def _override_responses(
        self, overrides: list[TargetingOverride], emails: dict[str, str]
    ) -> list[OverrideResponse]:
        user_emails = await self._repo.emails({o.subject_id for o in overrides if o.subject_type == "user"})
        workspaces = await self._repo.workspace_names({o.subject_id for o in overrides if o.subject_type == "workspace"})
        labels = {**user_emails, **workspaces}
        return [
            OverrideResponse(
                subject_type=override.subject_type, subject_id=override.subject_id,
                subject_label=labels.get(override.subject_id, override.subject_id), value=override.value,
                reason=override.reason, expires_at=override.expires_at,
                created_by_email=emails.get(override.created_by) if override.created_by else None,
                created_at=override.created_at,
            )
            for override in overrides
        ]

    # -- config --------------------------------------------------------------------------

    async def list_configs(self) -> AdminConfigListResponse:
        rows = await self._repo.configs()
        counts = await self._repo.override_counts("config")
        emails = await self._repo.emails({row.updated_by for row in rows.values()})
        return AdminConfigListResponse(
            configs=[
                AdminConfigSummary(**self._config_summary(definition, rows.get(key), counts, emails))
                for key, definition in CONFIGS.items()
            ]
        )

    async def get_config(self, key: str) -> AdminConfigDetailResponse:
        definition = _config_definition(key)
        row = await self._repo.config(key)
        overrides = await self._repo.overrides("config", key)
        emails = await self._repo.emails(
            {row.updated_by if row else None} | {override.created_by for override in overrides}
        )
        snapshot = await flags.snapshot_for(self._session)
        return AdminConfigDetailResponse(
            **self._config_summary(definition, row, {key: len(overrides)}, emails),
            rules=[ConfigRule.model_validate(rule) for rule in (row.rules if row else [])],
            overrides=await self._override_responses(overrides, emails),
            by_plan={plan: Evaluator(snapshot, FlagContext(plan=plan)).config(key).value for plan in PLANS},
        )

    @staticmethod
    def _config_summary(
        definition: ConfigDefinition, row: RemoteConfig | None, counts: dict[str, int], emails: dict[str, str]
    ) -> dict[str, Any]:
        return {
            "key": definition.key, "label": definition.label, "description": definition.description,
            "owner": definition.owner, "kind": definition.kind, "unit": definition.unit,
            "minimum": definition.minimum, "maximum": definition.maximum, "choices": list(definition.choices),
            "targeting": definition.targeting, "client": definition.client, "plan_promise": definition.plan_promise,
            "code_default": definition.default, "default_value": row.default_value if row else None,
            "rule_count": len(row.rules) if row else 0, "override_count": counts.get(definition.key, 0),
            "version": row.version if row else 0, "updated_at": row.updated_at if row else None,
            "updated_by_email": emails.get(row.updated_by) if row and row.updated_by else None,
        }

    async def update_config(self, key: str, body: AdminConfigUpdateRequest) -> AdminConfigDetailResponse:
        definition = _config_definition(key)
        if body.rules and definition.targeting == "global":
            raise _invalid(f"{key} is global and takes no rules.", "rules", "CONFIG_INVALID")
        await self._validate_rules(body.rules)
        default_value = (
            None if body.default_value is None else self._config_value(definition, body.default_value, "default_value")
        )
        rules = [
            {**rule.model_dump(), "serve": self._config_value(definition, rule.serve, f"rules.{rule.id}.serve")}
            for rule in body.rules
        ]
        row = await self._repo.config(key, lock=True)
        _check_version(row.version if row else 0, body.expected_version)
        before = _config_state(row)
        if row is None:
            row = RemoteConfig(key=key, version=0)
            self._session.add(row)
        row.default_value, row.rules = default_value, rules
        row.version += 1
        row.updated_by, row.updated_at = self._actor_id, datetime.utcnow()
        await self._commit("config.update", "config", key, before, _config_state(row), body.reason)
        return await self.get_config(key)

    @staticmethod
    def _config_value(definition: ConfigDefinition, value: Any, field: str) -> Any:
        try:
            return definition.validate(value)
        except ConfigValueError as exc:
            raise _invalid(str(exc), field, "CONFIG_INVALID") from exc

    # -- segments ------------------------------------------------------------------------

    async def list_segments(self) -> AdminSegmentListResponse:
        return AdminSegmentListResponse(segments=[self._segment(row) for row in await self._repo.segments()])

    async def update_segment(self, key: str, body: AdminSegmentUpdateRequest) -> AdminSegmentListResponse:
        row = await self._repo.segment(key, lock=True)
        if row is None:
            raise _not_found("segment")
        _check_version(row.version, body.expected_version)
        before = _segment_state(row)
        added = await self._user_ids(body.add_users, "add_users")
        removed = await self._user_ids(body.remove_users, "remove_users")
        row.user_ids = sorted((set(row.user_ids) | added) - removed)
        if body.email_domains is not None:
            row.email_domains = sorted({domain.strip().lower().lstrip("@") for domain in body.email_domains})
        if body.roles is not None:
            if unknown := set(body.roles) - set(ROLES):
                raise _invalid(f"Unknown roles: {', '.join(sorted(unknown))}", "roles")
            row.roles = sorted(set(body.roles))
        row.version += 1
        row.updated_by, row.updated_at = self._actor_id, datetime.utcnow()
        await self._commit("segment.update", "segment", key, before, _segment_state(row), body.reason)
        return await self.list_segments()

    async def _user_ids(self, refs: Iterable[str], field: str) -> set[str]:
        ids = set()
        for ref in refs:
            user = await self._repo.find_user(ref)
            if user is None:
                raise _invalid("Unknown user", field)
            ids.add(user.id)
        return ids

    @staticmethod
    def _segment(row: FlagSegment) -> AdminSegmentResponse:
        return AdminSegmentResponse(
            key=row.key, description=row.description, user_count=len(row.user_ids),
            email_domains=list(row.email_domains), roles=list(row.roles), version=row.version,
        )

    # -- audit ---------------------------------------------------------------------------

    async def audit_page(self, target_key: str | None, cursor: str | None) -> AdminAuditPageResponse:
        if cursor is not None and not cursor.isdigit():
            raise _invalid("Invalid cursor", "cursor")
        rows = await self._repo.audit_page(target_key, int(cursor) if cursor else None, AUDIT_PAGE_SIZE + 1)
        page = rows[:AUDIT_PAGE_SIZE]
        return AdminAuditPageResponse(
            entries=[AdminAuditEntry.model_validate(row, from_attributes=True) for row in page],
            next_cursor=str(page[-1].id) if len(rows) > AUDIT_PAGE_SIZE else None,
        )

    # -- legacy admin list ---------------------------------------------------------------

    async def legacy_list(self) -> AdminFeatureFlagListResponse:
        """GET /admin/features: the 13 pre-revamp keys, in the old shape."""
        rows = await self._repo.flags()
        evaluator = Evaluator(await flags.snapshot_for(self._session), GLOBAL_CONTEXT)
        return AdminFeatureFlagListResponse(
            flags=[
                AdminFeatureFlagResponse(
                    key=definition.key,
                    label=definition.label,
                    description=definition.description,
                    parent=definition.parent,
                    enabled=bool(rows.get(key) and rows[key].enabled),
                    effective=bool(evaluator.flag(key).value),
                    updated_at=rows[key].updated_at if key in rows else None,
                )
                for key, definition in FLAGS.items()
                if key in LEGACY_KEYS
            ]
        )

    # -- shared --------------------------------------------------------------------------

    @property
    def _actor_id(self) -> str | None:
        return self._actor.id if self._actor else None

    async def _validate_rules(self, rules: Iterable[FlagRule]) -> None:
        rules = list(rules)
        if len({rule.id for rule in rules}) != len(rules):
            raise _invalid("Rule ids must be unique.", "rules")
        segments = await self._repo.segment_keys() if any(rule.when.segments for rule in rules) else set()
        for rule in rules:
            if unknown := set(rule.when.segments) - segments:
                raise _invalid(f"Unknown segments: {', '.join(sorted(unknown))}", f"rules.{rule.id}.when.segments")
            if unknown := set(rule.when.plans) - set(PLANS):
                raise _invalid(f"Unknown plans: {', '.join(sorted(unknown))}", f"rules.{rule.id}.when.plans")

    async def _commit(
        self,
        action: str,
        target_kind: str,
        target_key: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        reason: str,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        """Audit row, version bump and NOTIFY, all in the change's own transaction."""
        actor = self._actor or AuditActor(None, None)
        self._repo.audit(
            actor_id=actor.id, actor_email=actor.email, action=action, target_kind=target_kind,
            target_key=target_key, subject_type=subject_type, subject_id=subject_id, before=before, after=after,
            reason=reason, request_id=actor.request_id, ip=actor.ip,
        )
        await self._repo.bump_version()
        await self._session.commit()
        await flags.after_write(self._session)
