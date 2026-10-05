"""Pure flag and config evaluation against an immutable snapshot. No I/O.

Flag order (06-flags §3.5), first match wins:

1. unknown key                         -> KeyError
2. the flag is killed                  -> off, KILLED
3. an ancestor or requirement is off   -> off, ANCESTOR_OFF / REQUIREMENT_OFF (blocked_by names the root cause)
4. no stored row                       -> the definition's default, DEFAULT
5. targeting switched off              -> off, TARGETING_OFF
6. user override                       -> its value, USER_OVERRIDE
7. workspace override                  -> its value, WORKSPACE_OVERRIDE
8. first matching rule                 -> rule.serve, RULE
9. fallthrough percentage              -> ROLLOUT_IN / ROLLOUT_OUT

Step 3 evaluates each ancestor with the same context and its full rules, at
any depth. The exception is ``flags.legacy_parent_semantics`` (remote config,
default on): while it is on, the 13 pre-revamp keys keep their old one-level
rule -- only the direct parent's own state counts, so a grandchild can stay on
while its grandparent is off (the bug in 06-flags §1.3). It stays on until the
owner has reviewed scripts/check_grandchild_flags.sql against production.
Kills cascade to every depth in both modes; nothing could be killed before.

Config order: user override, workspace override, first matching rule, the
built-in plan value, the stored default, the code default.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from functools import cached_property
from typing import Any, Iterable, Mapping

from pydantic import ValidationError

from core.logging_config import get_logger
from feature_flags.config_registry import (
    CONFIGS,
    FLAGS_LEGACY_PARENT_SEMANTICS,
    ConfigDefinition,
    ConfigValue,
    ConfigValueError,
)
from feature_flags.context import GLOBAL_CONTEXT, FlagContext
from feature_flags.registry import FLAGS, LEGACY_KEYS, FlagDefinition, ancestors
from feature_flags.schema import ConfigRule, EvalReason, FlagRule

log = get_logger(__name__)

BUCKETS = 10000
OverrideKey = tuple[str, str]  # (subject_type, subject_id)
TargetKey = tuple[str, str]    # (target_kind, target_key)


def bucket(salt: str, unit_id: str) -> int:
    """Stable bucket 0..9999. Changing this reshuffles every rollout, so it is pinned by golden tests."""
    digest = hashlib.sha256(f"{salt}:{unit_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % BUCKETS


def in_rollout(rollout_bps: int, salt: str, unit_id: str | None) -> tuple[bool, int | None]:
    """Whether ``unit_id`` falls inside ``rollout_bps``. 0% and 100% need no unit."""
    if rollout_bps >= BUCKETS:
        return True, None
    if rollout_bps <= 0 or unit_id is None:
        return False, None
    position = bucket(salt, unit_id)
    return position < rollout_bps, position


@dataclass(frozen=True)
class Condition:
    segments: frozenset[str] = frozenset()
    plans: frozenset[str] = frozenset()
    user_ids: frozenset[str] = frozenset()
    workspace_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Rule:
    id: str
    when: Condition
    serve: ConfigValue
    rollout_bps: int = BUCKETS

    @classmethod
    def parse(cls, raw: Mapping[str, Any], model: type[FlagRule]) -> Rule:
        rule = model.model_validate(raw)
        when = rule.when
        return cls(
            id=rule.id,
            when=Condition(*(frozenset(values) for values in (when.segments, when.plans, when.user_ids,
                                                              when.workspace_ids))),
            serve=rule.serve,
            rollout_bps=rule.rollout_bps,
        )


@dataclass(frozen=True)
class FlagState:
    enabled: bool
    rollout_bps: int = BUCKETS
    rules: tuple[Rule, ...] = ()
    salt: str | None = None
    killed: bool = False


@dataclass(frozen=True)
class ConfigState:
    default_value: ConfigValue | None = None
    rules: tuple[Rule, ...] = ()


@dataclass(frozen=True)
class Segment:
    user_ids: frozenset[str] = frozenset()
    email_domains: frozenset[str] = frozenset()
    roles: frozenset[str] = frozenset()

    def matches(self, ctx: FlagContext) -> bool:
        domain = ctx.email.rsplit("@", 1)[-1].lower() if ctx.email and "@" in ctx.email else None
        return (
            (ctx.user_id is not None and ctx.user_id in self.user_ids)
            or (ctx.role is not None and ctx.role in self.roles)
            or (domain is not None and domain in self.email_domains)
        )


@dataclass(frozen=True)
class Override:
    value: ConfigValue
    expires_at: datetime | None = None


@dataclass(frozen=True)
class Snapshot:
    """Everything evaluation needs, loaded at once and swapped atomically."""

    version: int = 0
    flags: Mapping[str, FlagState] = field(default_factory=dict)
    configs: Mapping[str, ConfigState] = field(default_factory=dict)
    segments: Mapping[str, Segment] = field(default_factory=dict)
    overrides: Mapping[TargetKey, Mapping[OverrideKey, Override]] = field(default_factory=dict)
    loaded_at: float = field(default_factory=time.monotonic)

    def _rules(self) -> Iterable[Rule]:
        for state in (*self.flags.values(), *self.configs.values()):
            yield from state.rules

    @cached_property
    def needs_user(self) -> bool:
        """A rule references a segment that matches by role or email domain."""
        referenced = {name for rule in self._rules() for name in rule.when.segments}
        return any(
            (segment := self.segments.get(name)) is not None and bool(segment.roles or segment.email_domains)
            for name in referenced
        )

    @cached_property
    def flags_need_plan(self) -> bool:
        return any(rule.when.plans for state in self.flags.values() for rule in state.rules)

    @cached_property
    def needs_plan(self) -> bool:
        """Evaluating every flag and config value needs the caller's plan."""
        return (
            self.flags_need_plan
            or any(rule.when.plans for state in self.configs.values() for rule in state.rules)
            or any(config.plan_defaults for config in CONFIGS.values())
        )

    def with_forced(self, flags: Mapping[str, bool], config: Mapping[str, ConfigValue]) -> Snapshot:
        """A copy where ``flags`` and ``config`` hold for everyone (tests and development).
        Hierarchy still applies: a forced child of an off parent stays off."""
        forced_rule = (lambda value: (Rule("r_forced", Condition(), value),))
        flag_states = {**self.flags, **{key: FlagState(enabled=on) for key, on in flags.items()}}
        config_states = {
            **self.configs,
            **{key: ConfigState(value, forced_rule(value)) for key, value in config.items()},
        }
        forced = {("flag", key) for key in flags} | {("config", key) for key in config}
        overrides = {target: values for target, values in self.overrides.items() if target not in forced}
        return replace(self, flags=flag_states, configs=config_states, overrides=overrides)


EMPTY_SNAPSHOT = Snapshot()


def build_snapshot(
    version: int,
    flag_rows: Iterable[Mapping[str, Any]] = (),
    config_rows: Iterable[Mapping[str, Any]] = (),
    segment_rows: Iterable[Mapping[str, Any]] = (),
    override_rows: Iterable[Mapping[str, Any]] = (),
) -> Snapshot:
    """A snapshot from stored rows. Unknown keys and invalid values are skipped and logged,
    so a bad row can never take down evaluation."""
    flags: dict[str, FlagState] = {}
    for row in flag_rows:
        if row["key"] in FLAGS:
            flags[row["key"]] = FlagState(
                enabled=bool(row["enabled"]),
                rollout_bps=row.get("rollout_bps", BUCKETS),
                rules=_parse_rules(row["key"], row.get("rules") or (), FlagRule),
                salt=row.get("bucket_salt"),
                killed=bool(row.get("killed", False)),
            )
    configs: dict[str, ConfigState] = {}
    for row in config_rows:
        definition = CONFIGS.get(row["key"])
        if definition is not None:
            configs[row["key"]] = ConfigState(
                default_value=_valid_value(definition, row.get("default_value")),
                rules=_config_rules(definition, row.get("rules") or ()),
            )
    segments = {
        row["key"]: Segment(
            frozenset(row.get("user_ids") or ()),
            frozenset(domain.lower() for domain in row.get("email_domains") or ()),
            frozenset(row.get("roles") or ()),
        )
        for row in segment_rows
    }
    overrides: dict[TargetKey, dict[OverrideKey, Override]] = {}
    for row in override_rows:
        target = (row["target_kind"], row["target_key"])
        value = _override_value(*target, row["value"])
        if value is not None:
            overrides.setdefault(target, {})[(row["subject_type"], row["subject_id"])] = Override(
                value, row.get("expires_at")
            )
    return Snapshot(version, flags, configs, segments, overrides)


def _parse_rules(key: str, raw_rules: Iterable[Mapping[str, Any]], model: type[FlagRule]) -> tuple[Rule, ...]:
    rules = []
    for raw in raw_rules:
        try:
            rules.append(Rule.parse(raw, model))
        except ValidationError:
            log.error(f"Ignoring an invalid stored rule on {key}")
    return tuple(rules)


def _config_rules(definition: ConfigDefinition, raw_rules: Iterable[Mapping[str, Any]]) -> tuple[Rule, ...]:
    if definition.targeting == "global":
        return ()
    rules = []
    for rule in _parse_rules(definition.key, raw_rules, ConfigRule):
        value = _valid_value(definition, rule.serve)
        if value is not None:
            rules.append(replace(rule, serve=value))
    return tuple(rules)


def _valid_value(definition: ConfigDefinition, value: Any) -> ConfigValue | None:
    if value is None:
        return None
    try:
        return definition.validate(value)
    except ConfigValueError:
        log.error(f"Ignoring an invalid stored value for {definition.key}; using the code default")
        return None


def _override_value(kind: str, key: str, value: Any) -> ConfigValue | None:
    if kind == "flag":
        return value if key in FLAGS and isinstance(value, bool) else None
    definition = CONFIGS.get(key)
    if definition is None or definition.targeting == "global":
        return None
    return _valid_value(definition, value)


@dataclass(frozen=True)
class Evaluation:
    key: str
    value: ConfigValue
    reason: EvalReason
    rule_id: str | None = None
    blocked_by: str | None = None
    bucket: int | None = None


class Evaluator:
    """Evaluates flags and config for one context. Memoises ancestors within one call chain."""

    def __init__(self, snapshot: Snapshot, ctx: FlagContext = GLOBAL_CONTEXT, now: datetime | None = None) -> None:
        self._snapshot = snapshot
        self._ctx = ctx
        self._now = now or datetime.utcnow()
        self._memo: dict[str, Evaluation] = {}
        # A global-only key: the loader drops rules and overrides, so the context cannot change it.
        self._legacy_parents = bool(self.config(FLAGS_LEGACY_PARENT_SEMANTICS).value)

    # -- flags ---------------------------------------------------------------------------

    def flag(self, key: str) -> Evaluation:
        if key in self._memo:
            return self._memo[key]
        definition = FLAGS[key]  # KeyError for an undeclared flag
        state = self._snapshot.flags.get(key)
        if state is not None and state.killed:
            result = Evaluation(key, False, "KILLED")
        else:
            result = self._blocked(definition) or self._own(definition, state)
        self._memo[key] = result
        return result

    def _blocked(self, definition: FlagDefinition) -> Evaluation | None:
        key = definition.key
        if self._legacy_parents and key in LEGACY_KEYS:
            return self._legacy_blocked(definition)
        if definition.parent is not None and not (parent := self.flag(definition.parent)).value:
            return Evaluation(key, False, "ANCESTOR_OFF", blocked_by=parent.blocked_by or definition.parent)
        for requirement in definition.requires:
            if not (required := self.flag(requirement)).value:
                return Evaluation(key, False, "REQUIREMENT_OFF", blocked_by=required.blocked_by or requirement)
        return None

    def _legacy_blocked(self, definition: FlagDefinition) -> Evaluation | None:
        """Pre-revamp rule: only the direct parent's own state, but kills cascade from any depth."""
        for ancestor in ancestors(definition.key):
            state = self._snapshot.flags.get(ancestor)
            if state is not None and state.killed:
                return Evaluation(definition.key, False, "ANCESTOR_OFF", blocked_by=ancestor)
        parent = definition.parent
        if parent is not None and not self._own(FLAGS[parent], self._snapshot.flags.get(parent)).value:
            return Evaluation(definition.key, False, "ANCESTOR_OFF", blocked_by=parent)
        return None

    def _own(self, definition: FlagDefinition, state: FlagState | None) -> Evaluation:
        """Steps 4-9: the flag's own targeting, ignoring its ancestors."""
        key = definition.key
        if state is None:
            return Evaluation(key, definition.default, "DEFAULT")
        if not state.enabled:
            return Evaluation(key, False, "TARGETING_OFF")
        if overridden := self._override("flag", key):
            return overridden
        salt = state.salt or key
        unit = self._unit(definition.bucket_by)
        for rule in state.rules:
            matched, position = self._matches(rule, salt, unit)
            if matched:
                return Evaluation(key, bool(rule.serve), "RULE", rule_id=rule.id, bucket=position)
        on, position = in_rollout(state.rollout_bps, salt, unit)
        return Evaluation(key, on, "ROLLOUT_IN" if on else "ROLLOUT_OUT", bucket=position)

    # -- config --------------------------------------------------------------------------

    def config(self, key: str) -> Evaluation:
        definition = CONFIGS[key]  # KeyError for an undeclared key
        state = self._snapshot.configs.get(key) or ConfigState()
        if overridden := self._override("config", key):
            return overridden
        for rule in state.rules:
            if self._matches(rule, key, self._unit("user"))[0]:
                return Evaluation(key, rule.serve, "RULE", rule_id=rule.id)
        for value in (definition.plan_default(self._ctx.plan), state.default_value, definition.default):
            if value is not None:
                return Evaluation(key, value, "DEFAULT")
        raise AssertionError("unreachable: every config definition has a default")

    # -- shared --------------------------------------------------------------------------

    def _override(self, kind: str, key: str) -> Evaluation | None:
        values = self._snapshot.overrides.get((kind, key))
        if not values:
            return None
        for subject_type, subject_id, reason in (
            ("user", self._ctx.user_id, "USER_OVERRIDE"),
            ("workspace", self._ctx.workspace_id, "WORKSPACE_OVERRIDE"),
        ):
            override = values.get((subject_type, subject_id)) if subject_id else None
            if override is not None and (override.expires_at is None or override.expires_at > self._now):
                return Evaluation(key, override.value, reason)
        return None

    def _unit(self, bucket_by: str) -> str | None:
        ctx = self._ctx
        if bucket_by == "workspace" and ctx.workspace_id:
            return ctx.workspace_id
        return ctx.user_id or ctx.anon_id

    def _matches(self, rule: Rule, salt: str, unit: str | None) -> tuple[bool, int | None]:
        when, ctx = rule.when, self._ctx
        if when.segments and not any(
            (segment := self._snapshot.segments.get(name)) is not None and segment.matches(ctx)
            for name in when.segments
        ):
            return False, None
        for allowed, value in (
            (when.plans, ctx.plan), (when.user_ids, ctx.user_id), (when.workspace_ids, ctx.workspace_id),
        ):
            if allowed and value not in allowed:
                return False, None
        return in_rollout(rule.rollout_bps, salt, unit)
