/**
 * Wire types for the editor. Existing routes mirror backend/editor/schema.py field for field;
 * the rest mirror docs/revamp/architecture/openapi.yaml and events.md, and are marked with the
 * NEEDS-BACKEND id from docs/revamp/screens/02-editor.md §18.2 until the backend ships them.
 * Every Timeline position is whole frames (lib/editor/timeline.ts).
 */
import type { Timeline, TimelineOp } from '@/lib/editor/timeline';

/* ───────────── existing: backend/editor/schema.py ───────────── */

export type EditorAspect = '9:16' | '1:1' | '4:5' | '16:9';

/** EditorProjectCreate. */
export interface EditorProjectCreate {
  title?: string;
  aspect?: EditorAspect;
}

/** EditorProjectSummary. Datetimes are ISO strings. */
export interface EditorProjectSummary {
  id: string;
  title: string;
  version: number;
  /** Seconds. */
  duration_s: number;
  created_at: string;
  updated_at: string;
}

/** EditorProjectResponse. */
export interface EditorProject extends EditorProjectSummary {
  timeline: Timeline;
}

/** EditorOpsRequest. */
export interface EditorOpsRequest {
  base_version: number;
  ops: TimelineOp[];
}

/** EditorOpsResponse. */
export interface EditorOpsResponse {
  version: number;
  timeline: Timeline;
}

/* ───────────── shared run vocabulary (openapi components) ───────────── */

export type RunMode = 'edit' | 'ask' | 'plan';

export type RunStatus =
  | 'queued'
  | 'acknowledged'
  | 'planning'
  | 'awaiting_input'
  | 'executing'
  | 'paused'
  | 'stopping'
  | 'checking'
  | 'succeeded'
  | 'partial'
  | 'failed'
  | 'cancelled';

export const TERMINAL_RUN_STATUSES: ReadonlySet<RunStatus> = new Set(['succeeded', 'partial', 'failed', 'cancelled']);

/**
 * openapi ContextChip. `region` is NEEDS-BACKEND: EB-9.
 * clip → {item_id}; range → {start_frame, end_frame}; caption_line → {start_frame, end_frame, text?};
 * asset → {media_asset_id} | {broll_asset_id}; moment → {frame}; region → {frame, bbox}.
 */
export type WireChip =
  | { type: 'clip'; ref: { item_id: string }; label?: string }
  | { type: 'range'; ref: { start_frame: number; end_frame: number }; label?: string }
  | { type: 'caption_line'; ref: { start_frame: number; end_frame: number; text?: string }; label?: string }
  | { type: 'asset'; ref: { media_asset_id: string } | { broll_asset_id: string }; label?: string }
  | { type: 'moment'; ref: { frame: number }; label?: string }
  | { type: 'region'; ref: { frame: number; bbox: Bbox }; label?: string };

/** Shares of the frame, 0–1. */
export interface Bbox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Credits {
  estimate: number;
  held: number;
  spent: number;
}

/** openapi Error / events.md ErrorObject. */
export interface ErrorObject {
  code: string;
  message: string;
  details?: Record<string, unknown> | unknown[];
  request_id?: string;
  retryable: boolean;
}

export interface Suggestion {
  label: string;
  prompt: string;
}

export interface PlanStepOutline {
  id: string;
  label: string;
}

/** NEEDS-BACKEND: EB-7. A timestamp citation, referenced in text as `[[c1]]`. */
export interface Citation {
  id: string;
  start_f: number;
  end_f: number;
  item_id?: string;
  text: string;
}

/** NEEDS-BACKEND: EB-8. One card of the source strip. */
export interface FindingItem {
  id: string;
  start_f: number;
  end_f: number;
  /** "Story", "Hot take", "Pouring coffee". */
  label: string;
  tag?: string;
  score?: number;
  poster_url?: string;
}

/** NEEDS-BACKEND: EB-21. What a turn produced, for the Outputs tab. */
export interface RunOutput {
  kind: 'version' | 'render' | 'caption_file' | 'thumbnail';
  id: string;
  label: string;
  url?: string;
  job_id?: string;
}

/** openapi VersionSummary. NEEDS-BACKEND: EB-10. */
export interface VersionSummary {
  id: string;
  project_id: string;
  kind: 'ai_run' | 'hand' | 'restore' | 'undo' | 'import';
  name: string;
  /** "user" or "agent:editor". */
  author: string;
  created_by?: string;
  run_id?: string | null;
  base_revision: number;
  result_revision: number;
  restored_from_version_id?: string | null;
  thumbnail_path?: string | null;
  bookmarked: boolean;
  created_at: string;
}

/** openapi Version. NEEDS-BACKEND: EB-10. */
export interface Version extends VersionSummary {
  timeline: Timeline;
}

/** openapi VersionCompare. NEEDS-BACKEND: EB-11. */
export interface VersionCompare {
  from: { version_id: string; revision: number; timeline: Timeline };
  to: { version_id: string; revision: number; timeline: Timeline };
  changed_ranges: [number, number][];
  changes: { text: string; item_ids: string[] }[];
}

/** openapi RevisionResult. NEEDS-BACKEND: EB-10. */
export interface RevisionResult {
  revision: number;
  timeline: Timeline;
  version?: VersionSummary | null;
}

/** openapi RunStep (snapshot form; the live form comes from events). */
export interface RunStepSnapshot {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  summary?: string | null;
  revisions?: number[];
}

export interface RunQuestion {
  question_id: string;
  text: string;
  choices: { id: string; label: string; hint?: string }[];
  expires_at?: string;
}

/** openapi Run. NEEDS-BACKEND: EB-3. */
export interface Run {
  id: string;
  project_id: string;
  workspace_id?: string;
  user_id?: string;
  status: RunStatus;
  mode: RunMode;
  prompt: string;
  chips?: WireChip[];
  queue_position?: number | null;
  base_revision?: number | null;
  last_revision?: number | null;
  plan?: { sentences: string[]; steps: RunStepSnapshot[] } | null;
  question?: RunQuestion | null;
  pause?: { reason: 'credits' | 'approval'; needed?: number; text?: string } | null;
  summary?: {
    done: string[];
    not_done: { text: string; reason: string }[];
    answer?: string;
    suggestions?: Suggestion[];
  } | null;
  version?: VersionSummary | null;
  error?: ErrorObject | null;
  credits: Credits;
  retry_of_run_id?: string | null;
  last_event_seq: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

/** openapi RunCreate. NEEDS-BACKEND: EB-3 (`approved_plan`: EB-5). */
export interface RunCreate {
  prompt: string;
  mode: RunMode;
  chips?: WireChip[];
  rewind_to_version_id?: string;
  approved_plan?: { from_run_id: string; sentences: string[]; steps: PlanStepOutline[] };
}

/** POST …/runs/estimate response. NEEDS-BACKEND: EB-4. */
export interface RunEstimate {
  credits: number;
  free: boolean;
  needs_approval: boolean;
  balance?: number;
}

/** openapi ActivityItem. NEEDS-BACKEND: EB-6. Jobs are left opaque until lib/api/jobs types them. */
export interface ActivityItem {
  kind: 'run' | 'job' | 'version';
  id: string;
  at: string;
  run?: Run;
  job?: Record<string, unknown>;
  version?: VersionSummary;
}

/** NEEDS-BACKEND: EB-18. One transcript word with times in the source asset (frames). */
export interface EditorTranscriptWord {
  text: string;
  asset: string;
  start_f: number;
  end_f: number;
  speaker?: string | null;
}

export interface EditorTranscript {
  words: EditorTranscriptWord[];
}

/* ───────────── run events (events.md §1, §3) ───────────── */

type RunEventData = {
  'run.queued': { queue_position: number; prompt_preview: string };
  'run.queue.updated': { queue_position: number };
  'run.acknowledged': { status: 'acknowledged'; mode: RunMode; chips: WireChip[]; base_revision: number; credits: Credits };
  'run.plan.delta': { text: string };
  'run.plan': {
    sentences: string[];
    steps: PlanStepOutline[];
    targets?: { clip_ids?: string[]; ranges?: [number, number][] };
    credits: Credits;
    needs_approval: boolean;
    citations?: Citation[];
  };
  'run.message.delta': { text: string; role: 'answer' | 'summary'; citations?: Citation[] };
  'run.finding': { kind: 'moment' | 'broll'; items: FindingItem[] };
  'run.question': RunQuestion & { allow_skip: true };
  'run.answered': { question_id: string; choice_id?: string; text?: string; skipped: boolean; by: 'user' | 'timeout' };
  'run.step.started': { step_id: string; index: number; total: number; label: string };
  'run.step.progress': { step_id: string; done?: number; total?: number; percent?: number; label?: string };
  'run.step.completed': { step_id: string; label: string; summary: string; revisions: number[] };
  'run.step.failed': { step_id: string; error: ErrorObject; will_retry: boolean; attempt: number };
  'run.lock.acquired': { step_id: string; item_ids: string[] };
  'run.lock.released': { step_id: string; item_ids: string[] };
  'run.operation.applied': {
    revision: number;
    base_revision: number;
    ops: TimelineOp[];
    changed_ranges: [number, number][];
    item_ids: string[];
    step_id: string;
    client_batch_id: string;
  };
  'run.check.started': Record<string, never>;
  'run.check.completed': { passed: boolean; findings: { severity: 'info' | 'warn'; text: string }[] };
  'run.paused': {
    reason: 'credits' | 'approval';
    credits: Credits;
    needed?: number;
    approval?: { kind: 'credits' | 'removal'; text: string; share_removed?: number };
    options: ('continue' | 'finish' | 'add_credits')[];
  };
  'run.resumed': { reason: 'user_continue' | 'credits_added' | 'worker_restart'; attempt?: number };
  'run.stop_requested': { by: string };
  'run.result': {
    status: 'succeeded' | 'partial';
    version: { id: string; name: string; result_revision: number } | null;
    summary: { done: string[]; not_done: { text: string; reason: string }[] };
    answer?: string;
    plan_document?: { sentences: string[]; steps: PlanStepOutline[] };
    suggestions: Suggestion[];
    credits: Credits;
    duration_ms: number;
    citations?: Citation[];
    outputs?: RunOutput[];
  };
  'run.failed': {
    error: ErrorObject;
    version: { id: string; name: string } | null;
    suggestion?: Suggestion;
    credits: Credits;
  };
  'run.cancelled': { by: 'user' | 'system'; while: 'queued' | 'running' };
};

export type RunEventType = keyof RunEventData;

/** The envelope fields the run store reads; anything else on the wire is ignored (events.md §8). */
interface RunEventEnvelope<K extends RunEventType> {
  type: K;
  v?: number;
  run_id: string;
  /** Gapless per run for durable events; the last durable seq for ephemeral ones. */
  seq: number;
  sub?: number;
  durable: boolean;
  ts?: string;
  data: RunEventData[K];
}

/** NEEDS-BACKEND: EB-1 (stream) / EB-3 (`GET /runs/{id}/events`). */
export type RunEvent = { [K in RunEventType]: RunEventEnvelope<K> }[RunEventType];

export type RunEventOf<K extends RunEventType> = Extract<RunEvent, { type: K }>;

/** Ephemeral types (events.md §2): never stored, only applied when their seq is current. */
export const EPHEMERAL_RUN_EVENTS: ReadonlySet<RunEventType> = new Set(['run.plan.delta', 'run.message.delta', 'run.step.progress']);
