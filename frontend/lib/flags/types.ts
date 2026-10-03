// Mirrors backend/feature_flags/schema.py exactly (06-flags §8.3). Hand-written until
// backend/scripts/export_openapi.py generates these (04-architecture R11).
// The legacy /features types stay in lib/api.ts unchanged.

import type { ConfigKey, FlagKey } from './registry.gen';

export type ConfigValue = boolean | number | string;
export type SubjectType = 'user' | 'workspace';
export type TargetKind = 'flag' | 'config' | 'segment';
export type FlagKind = 'release' | 'ops' | 'experiment';
export type LiveUpdate = 'immediate' | 'next_navigation';
export type ValueKind = 'int' | 'float' | 'bool' | 'string' | 'enum';
export type Unit = 'bytes' | 'seconds' | 'credits' | 'ratio' | 'count' | 'per_minute';
export type ConfigTargeting = 'plan' | 'global';
export type EvalReason =
  | 'KILLED'
  | 'ANCESTOR_OFF'
  | 'REQUIREMENT_OFF'
  | 'DEFAULT'
  | 'TARGETING_OFF'
  | 'USER_OVERRIDE'
  | 'WORKSPACE_OVERRIDE'
  | 'RULE'
  | 'ROLLOUT_IN'
  | 'ROLLOUT_OUT';

// --- public ---

export interface FlagsBootstrapResponse {
  version: number;
  evaluated_at: string;
  subject: 'user' | 'anonymous';
  flags: Partial<Record<FlagKey, boolean>>; // only client flags; absent => generated default
  config: Partial<Record<ConfigKey, ConfigValue>>;
  poll_seconds: number;
}

export interface FlagsChangedEvent {
  version: number;
  killed: FlagKey[];
}

// --- targeting ---

export interface TargetCondition {
  segments: string[];
  plans: string[];
  user_ids: string[];
  workspace_ids: string[];
}

export interface FlagRule {
  id: string;
  description: string;
  when: TargetCondition;
  rollout_bps: number;
  serve: boolean;
}

export interface ConfigRule extends Omit<FlagRule, 'serve'> {
  serve: ConfigValue;
}

export interface OverrideResponse {
  subject_type: SubjectType;
  subject_id: string;
  subject_label: string;
  value: ConfigValue;
  reason: string;
  expires_at: string | null;
  created_by_email: string | null;
  created_at: string;
}

// --- admin flags ---

export interface AdminFlagSummary {
  key: FlagKey;
  label: string;
  description: string;
  owner: string;
  kind: FlagKind;
  parent: FlagKey | null;
  requires: FlagKey[];
  default: boolean;
  client: boolean;
  public: boolean;
  live_update: LiveUpdate;
  created: string;
  expires: string | null;
  stale: boolean;
  enabled: boolean;
  killed: boolean;
  rollout_bps: number;
  rule_count: number;
  override_count: number;
  blocked_by: FlagKey | null;
  version: number;
  updated_at: string | null;
  updated_by_email: string | null;
}

export interface AdminFlagListResponse {
  flags: AdminFlagSummary[];
  snapshot_version: number;
}

export interface AdminFlagDetailResponse extends AdminFlagSummary {
  rules: FlagRule[];
  overrides: OverrideResponse[];
  children: FlagKey[];
  dependants: FlagKey[];
  killed_reason: string | null;
  killed_at: string | null;
  killed_by_email: string | null;
  exposures_7d: Record<string, number>;
}

export interface AdminReasonRequest {
  reason: string;
}

export interface AdminFlagUpdateRequest extends AdminReasonRequest {
  expected_version: number;
  enabled: boolean;
  rules: FlagRule[];
  rollout_bps: number;
}

export interface AdminFlagKillRequest extends AdminReasonRequest {
  confirm_key: FlagKey;
}

export interface AdminOverrideRequest extends AdminReasonRequest {
  subject_type: SubjectType;
  subject: string;
  value: ConfigValue;
  expires_at?: string | null;
}

export interface AdminEvaluateRequest {
  user?: string | null;
  workspace_id?: string | null;
}

export interface AdminEvaluationResponse {
  key: FlagKey | ConfigKey;
  value: ConfigValue;
  reason: EvalReason;
  rule_id: string | null;
  blocked_by: FlagKey | null;
  bucket: number | null;
}

export interface AdminFlagsHealthResponse {
  snapshot_version: number;
  snapshot_age_seconds: number;
  listening: boolean;
}

// --- audit ---

export interface AdminAuditEntry {
  id: number;
  at: string;
  actor_email: string | null;
  action: string;
  target_kind: TargetKind;
  target_key: string;
  subject_type: SubjectType | null;
  subject_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string;
}

export interface AdminAuditPageResponse {
  entries: AdminAuditEntry[];
  next_cursor: string | null;
}

// --- admin config ---

export interface AdminConfigSummary {
  key: ConfigKey;
  label: string;
  description: string;
  owner: string;
  kind: ValueKind;
  unit: Unit | null;
  minimum: number | null;
  maximum: number | null;
  choices: string[];
  targeting: ConfigTargeting;
  client: boolean;
  plan_promise: boolean;
  code_default: ConfigValue;
  default_value: ConfigValue | null;
  rule_count: number;
  override_count: number;
  version: number;
  updated_at: string | null;
  updated_by_email: string | null;
}

export interface AdminConfigListResponse {
  configs: AdminConfigSummary[];
}

export interface AdminConfigDetailResponse extends AdminConfigSummary {
  rules: ConfigRule[];
  overrides: OverrideResponse[];
  by_plan: Record<string, ConfigValue>;
}

export interface AdminConfigUpdateRequest extends AdminReasonRequest {
  expected_version: number;
  default_value: ConfigValue | null;
  rules: ConfigRule[];
}

// --- segments ---

export interface AdminSegmentResponse {
  key: string;
  description: string;
  user_count: number;
  email_domains: string[];
  roles: string[];
  version: number;
}

export interface AdminSegmentListResponse {
  segments: AdminSegmentResponse[];
}

export interface AdminSegmentUpdateRequest extends AdminReasonRequest {
  expected_version: number;
  add_users?: string[];
  remove_users?: string[];
  email_domains?: string[] | null;
  roles?: string[] | null;
}
