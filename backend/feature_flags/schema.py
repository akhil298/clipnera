from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# bool first, so True is never coerced to 1.
ConfigValue = Union[bool, int, float, str]
SubjectType = Literal["user", "workspace"]
TargetKind = Literal["flag", "config", "segment"]
FlagKind = Literal["release", "ops", "experiment"]
LiveUpdate = Literal["immediate", "next_navigation"]
ValueKind = Literal["int", "float", "bool", "string", "enum"]
Unit = Literal["bytes", "seconds", "credits", "ratio", "count", "per_minute"]
ConfigTargeting = Literal["plan", "global"]
EvalReason = Literal[
    "KILLED", "ANCESTOR_OFF", "REQUIREMENT_OFF", "DEFAULT", "TARGETING_OFF",
    "USER_OVERRIDE", "WORKSPACE_OVERRIDE", "RULE", "ROLLOUT_IN", "ROLLOUT_OUT",
]
AuditAction = Literal[
    "flag.update", "flag.kill", "flag.unkill", "flag.reshuffle", "override.set", "override.delete",
    "config.update", "segment.update", "legacy.switch", "legacy.import",
]


# --- legacy (unchanged shapes) ---------------------------------------------------------


class FeatureFlagsResponse(BaseModel):
    """Effective on/off state of every flag, for deciding what the UI shows."""

    flags: Dict[str, bool]


class AdminFeatureFlagResponse(BaseModel):
    key: str
    label: str
    description: str
    parent: Optional[str] = None
    # The switch as set; ``effective`` is false while the parent is off.
    enabled: bool
    effective: bool
    updated_at: Optional[datetime] = None


class AdminFeatureFlagListResponse(BaseModel):
    flags: List[AdminFeatureFlagResponse]


class AdminFeatureFlagUpdateRequest(BaseModel):
    enabled: bool


# --- public ---------------------------------------------------------------------------


class FlagsBootstrapResponse(BaseModel):
    version: int
    evaluated_at: datetime
    subject: Literal["user", "anonymous"]
    flags: Dict[str, bool]
    config: Dict[str, ConfigValue]
    poll_seconds: int


class FlagsChangedEvent(BaseModel):
    """Real-time payload, event name ``flags.changed``."""

    version: int
    killed: List[str] = []


# --- targeting ------------------------------------------------------------------------


class TargetCondition(BaseModel):
    segments: List[str] = []
    plans: List[str] = []
    user_ids: List[str] = []
    workspace_ids: List[str] = []


class FlagRule(BaseModel):
    id: str = Field(pattern=r"^r_[a-z0-9_]{1,32}$")
    description: str = Field("", max_length=200)
    when: TargetCondition
    rollout_bps: int = Field(10000, ge=0, le=10000)
    serve: bool


class ConfigRule(FlagRule):
    serve: ConfigValue  # validated against the definition's TypeAdapter


class OverrideResponse(BaseModel):
    subject_type: SubjectType
    subject_id: str
    subject_label: str  # email or workspace name, admin only
    value: ConfigValue
    reason: str
    expires_at: Optional[datetime] = None
    created_by_email: Optional[str] = None
    created_at: datetime


# --- admin flags ----------------------------------------------------------------------


class AdminFlagSummary(BaseModel):
    key: str
    label: str
    description: str
    owner: str
    kind: FlagKind
    parent: Optional[str] = None
    requires: List[str] = []
    default: bool
    client: bool
    public: bool
    live_update: LiveUpdate
    created: date
    expires: Optional[date] = None
    stale: bool  # past expires, or a release flag at 100% for more than 14 days
    enabled: bool
    killed: bool
    rollout_bps: int
    rule_count: int
    override_count: int
    blocked_by: Optional[str] = None  # nearest killed/off ancestor or requirement
    version: int
    updated_at: Optional[datetime] = None
    updated_by_email: Optional[str] = None


class AdminFlagListResponse(BaseModel):
    flags: List[AdminFlagSummary]
    snapshot_version: int


class AdminFlagDetailResponse(AdminFlagSummary):
    rules: List[FlagRule]
    overrides: List[OverrideResponse]
    children: List[str]
    dependants: List[str]
    killed_reason: Optional[str] = None
    killed_at: Optional[datetime] = None
    killed_by_email: Optional[str] = None
    exposures_7d: Dict[str, int] = {}


class AdminReasonRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class AdminFlagUpdateRequest(AdminReasonRequest):
    expected_version: int
    enabled: bool
    rules: List[FlagRule] = Field(default_factory=list, max_length=20)
    rollout_bps: int = Field(ge=0, le=10000)


class AdminFlagKillRequest(AdminReasonRequest):
    confirm_key: str  # must equal the path key


class AdminOverrideRequest(AdminReasonRequest):
    subject_type: SubjectType
    subject: str = Field(min_length=1, max_length=255)  # user email or id / workspace id
    value: ConfigValue
    expires_at: Optional[datetime] = None


class AdminEvaluateRequest(BaseModel):
    user: Optional[str] = None  # email or id; None = anonymous
    workspace_id: Optional[str] = None


class AdminEvaluationResponse(BaseModel):
    key: str
    value: ConfigValue
    reason: EvalReason
    rule_id: Optional[str] = None
    blocked_by: Optional[str] = None
    bucket: Optional[int] = None  # 0..9999


class AdminFlagsHealthResponse(BaseModel):
    snapshot_version: int
    snapshot_age_seconds: float
    listening: bool


# --- audit ----------------------------------------------------------------------------


class AdminAuditEntry(BaseModel):
    id: int
    at: datetime
    actor_email: Optional[str] = None
    action: str
    target_kind: TargetKind
    target_key: str
    subject_type: Optional[SubjectType] = None
    subject_id: Optional[str] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    reason: str


class AdminAuditPageResponse(BaseModel):
    entries: List[AdminAuditEntry]
    next_cursor: Optional[str] = None


# --- admin config ---------------------------------------------------------------------


class AdminConfigSummary(BaseModel):
    key: str
    label: str
    description: str
    owner: str
    kind: ValueKind
    unit: Optional[Unit] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    choices: List[str] = []
    targeting: ConfigTargeting
    client: bool
    plan_promise: bool
    code_default: ConfigValue
    default_value: Optional[ConfigValue] = None  # stored; None = code default
    rule_count: int
    override_count: int
    version: int
    updated_at: Optional[datetime] = None
    updated_by_email: Optional[str] = None


class AdminConfigListResponse(BaseModel):
    configs: List[AdminConfigSummary]


class AdminConfigDetailResponse(AdminConfigSummary):
    rules: List[ConfigRule]
    overrides: List[OverrideResponse]
    by_plan: Dict[str, ConfigValue]  # resolved value per plan, for the table view


class AdminConfigUpdateRequest(AdminReasonRequest):
    expected_version: int
    default_value: Optional[ConfigValue] = None
    rules: List[ConfigRule] = Field(default_factory=list, max_length=20)


# --- segments -------------------------------------------------------------------------


class AdminSegmentResponse(BaseModel):
    key: str
    description: str
    user_count: int
    email_domains: List[str]
    roles: List[str]
    version: int


class AdminSegmentListResponse(BaseModel):
    segments: List[AdminSegmentResponse]


class AdminSegmentUpdateRequest(AdminReasonRequest):
    expected_version: int
    add_users: List[str] = []  # emails or ids
    remove_users: List[str] = []
    email_domains: Optional[List[str]] = None
    roles: Optional[List[str]] = None
