"""Remote config: typed values an admin can change without a deploy.

Declared once here, like flags. A value is validated against its definition on
every admin write, every rule ``serve`` and every snapshot load; an invalid
stored value is ignored in favour of the code default.

Values that are product constants with pricing implications (credits per
minute, pack prices) stay in settings and entitlements on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Annotated, Any, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, TypeAdapter, ValidationError

from core.config import BaseConfig
from feature_flags.registry import BACKEND_LEAD, FRONTEND_LEAD, KEY_MAX_LENGTH, KEY_PATTERN, PRODUCT_OWNER

ValueKind = Literal["int", "float", "bool", "string", "enum"]
Unit = Literal["bytes", "seconds", "credits", "ratio", "count", "per_minute"]
ConfigTargeting = Literal["plan", "global"]
ConfigValue = bool | int | float | str

MIB = 1024 * 1024
GIB = 1024 * MIB
TIB = 1024 * GIB


class ConfigValueError(ValueError):
    pass


@dataclass(frozen=True)
class ConfigDefinition:
    key: str
    label: str
    description: str
    owner: str
    kind: ValueKind
    default: ConfigValue
    unit: Unit | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()              # enum only
    # "global" values take no rules or overrides: their readers (rate limiting,
    # the engine itself) must not depend on who is asking.
    targeting: ConfigTargeting = "global"
    # Built-in per-plan values, applied after admin rules and before the stored default.
    plan_defaults: tuple[tuple[str, ConfigValue], ...] = ()
    client: bool = False                       # sent in the bootstrap payload
    public: bool = False
    plan_promise: bool = False                 # shown to customers; read through entitlements

    @cached_property
    def adapter(self) -> TypeAdapter:
        bounds = Field(ge=self.minimum, le=self.maximum)
        annotation: Any = {
            "int": Annotated[StrictInt, bounds],
            "float": Annotated[float, bounds],
            "bool": StrictBool,
            "string": Annotated[StrictStr, Field(max_length=500)],
            "enum": Literal[self.choices] if self.choices else StrictStr,
        }[self.kind]
        return TypeAdapter(annotation)

    def validate(self, value: Any) -> ConfigValue:
        """``value`` as this definition's type, or ConfigValueError. ``True`` is never a number."""
        if self.kind != "bool" and isinstance(value, bool):
            raise ConfigValueError(f"{self.key} must be a {self.kind}, not a boolean")
        try:
            validated = self.adapter.validate_python(value)
        except ValidationError as exc:
            raise ConfigValueError(f"{self.key}: {exc.errors()[0]['msg']}") from exc
        return float(validated) if self.kind == "float" else validated

    def plan_default(self, plan: str | None) -> ConfigValue | None:
        return dict(self.plan_defaults).get(plan) if plan else None


FLAGS_LEGACY_PARENT_SEMANTICS = "flags.legacy_parent_semantics"
FLAGS_CLIENT_POLL_SECONDS = "flags.client_poll_seconds"

# The code default, not the environment's value, so the generated TypeScript is the same everywhere.
# uploads/ still reads settings.UPLOAD_MAX_BYTES until it moves to this key (06-flags §13 step 1.7).
_UPLOAD_MAX_BYTES = BaseConfig.model_fields["UPLOAD_MAX_BYTES"].default

_DEFINITIONS = (
    ConfigDefinition(
        "agent.approval_credit_threshold", "Approval threshold",
        "An Edit-mode run pauses for \"Go ahead\" when its estimate exceeds this many credits "
        "(30 minutes of source by default).",
        BACKEND_LEAD, "int", 60, unit="credits", minimum=0, maximum=10000, targeting="plan", client=True,
    ),
    ConfigDefinition(
        "agent.approval_timeline_removal_ratio", "Approval removal share",
        "A run pauses for approval when it would remove more than this share of the timeline.",
        BACKEND_LEAD, "float", 0.5, unit="ratio", minimum=0.05, maximum=1.0, targeting="plan", client=True,
    ),
    ConfigDefinition(
        "agent.checkin_credit_threshold", "Check-in threshold",
        "A running agent shows a check-in card once its actual spend crosses this many credits.",
        BACKEND_LEAD, "int", 60, unit="credits", minimum=0, maximum=10000, targeting="plan", client=True,
    ),
    ConfigDefinition(
        "agent.auto_retry_cap", "Automatic retries",
        "How many times the agent runtime retries a failed step on its own.",
        BACKEND_LEAD, "int", 1, unit="count", minimum=0, maximum=3,
    ),
    ConfigDefinition(
        "notifications.email_min_job_seconds", "Completion email threshold",
        "Jobs that take longer than this send an email when they finish.",
        BACKEND_LEAD, "int", 300, unit="seconds", minimum=0, maximum=86400, client=True,
    ),
    ConfigDefinition(
        "uploads.max_bytes", "Largest upload",
        "The largest video file a user may upload.",
        BACKEND_LEAD, "int", _UPLOAD_MAX_BYTES, unit="bytes", minimum=100 * MIB, maximum=50 * GIB,
        targeting="plan", client=True, plan_promise=True,
    ),
    ConfigDefinition(
        "storage.user_library_quota_bytes", "Personal B-roll storage",
        "Storage for a user's own B-roll uploads. Uploads are blocked past it; nothing is deleted.",
        PRODUCT_OWNER, "int", 1 * GIB, unit="bytes", minimum=0, maximum=1 * TIB, targeting="plan",
        plan_defaults=(("pro", 25 * GIB), ("pro_plus", 25 * GIB)), client=True, plan_promise=True,
    ),
    ConfigDefinition(
        "rate_limit.default_per_minute", "Default rate limit",
        "Requests per minute for APIs that declare no limit of their own.",
        BACKEND_LEAD, "int", 300, unit="per_minute", minimum=30, maximum=3000,
    ),
    ConfigDefinition(
        "rate_limit.agent_runs_per_minute", "Prompt rate limit",
        "Prompt submissions per minute per user.",
        BACKEND_LEAD, "int", 6, unit="per_minute", minimum=1, maximum=60,
    ),
    ConfigDefinition(
        FLAGS_CLIENT_POLL_SECONDS, "Flag poll interval",
        "How often an open tab refetches its flags while the real-time stream is disconnected.",
        FRONTEND_LEAD, "int", 60, unit="seconds", minimum=15, maximum=600, client=True,
    ),
    ConfigDefinition(
        FLAGS_LEGACY_PARENT_SEMANTICS, "Legacy parent check for the original 13 flags",
        "On: the 13 pre-revamp flags check only their direct parent's own switch, as before, so a "
        "grandchild can stay on while its grandparent is off. Off: every flag checks its whole ancestor "
        "chain. Turn off only after the pre-deploy check (scripts/check_grandchild_flags.sql) is reviewed.",
        BACKEND_LEAD, "bool", True,
    ),
)

CONFIGS: dict[str, ConfigDefinition] = {config.key: config for config in _DEFINITIONS}


def validate_config_registry(registry: dict[str, ConfigDefinition]) -> list[str]:
    problems: list[str] = []
    for key, config in registry.items():
        if len(key) > KEY_MAX_LENGTH or not KEY_PATTERN.match(key):
            problems.append(f"{key}: key must match {KEY_PATTERN.pattern}")
        if (config.kind == "enum") != bool(config.choices):
            problems.append(f"{key}: choices are required for enums and only for enums")
        if config.public and not config.client:
            problems.append(f"{key}: a public value must also be a client value")
        if config.plan_defaults and config.targeting != "plan":
            problems.append(f"{key}: plan defaults need plan targeting")
        for value in (config.default, *(value for _, value in config.plan_defaults)):
            try:
                config.validate(value)
            except ConfigValueError as exc:
                problems.append(f"{key}: invalid built-in value ({exc})")
    return problems


_problems = validate_config_registry(CONFIGS)
if _problems:
    raise RuntimeError("Invalid remote config registry: " + "; ".join(_problems))
