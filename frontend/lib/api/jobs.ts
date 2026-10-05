import { apiFetch } from './client';

/**
 * Typed wrappers for a project's run: pipeline status, cancel, resume, the
 * source download, and what the run cost. Shapes mirror the dicts built in
 * backend/pipeline/service.py (`_serialize_step`, `_status_payload`,
 * `_RunPlan.response`) and backend/clip/service.py (download progress); those
 * routes have no Pydantic schema yet (see the report's NEEDS-BACKEND list).
 */

/** backend/pipeline/model.py PipelineStepType. */
export type PipelineStepName =
  | 'download'
  | 'audio_extraction'
  | 'ai_noise_cancellation'
  | 'transcription'
  | 'topic_research'
  | 'visual_analysis'
  | 'content_classification'
  | 'highlight_detection'
  | 'bounding_box_detection'
  | 'scoring'
  | 'metadata_generation'
  | 'aspect_ratio_render'
  | 'clip_generation'
  | 'subtitle_styling'
  | 'burn_in_export'
  | 'depth_captions';

/** backend/pipeline/model.py StepStatus. */
export type PipelineStepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'reverted' | 'skipped';

/** `_serialize_step`. Timestamps are naive UTC ISO strings (no offset). */
export interface PipelineStepLog {
  step: PipelineStepName;
  status: PipelineStepStatus;
  progress_percent: number;
  message: string | null;
  artifact_path: string | null;
  started_at: string | null;
  finished_at: string | null;
}

/** `_overall_status`, plus `not_started` from `_not_started`. */
export type PipelineRunStatus = 'not_started' | 'pending' | 'running' | 'completed' | 'error';

/** GET /pipeline/status/{project_id}: `_status_payload` or `_not_started`. */
export interface PipelineStatus {
  project_id: string;
  status: PipelineRunStatus;
  current_step?: PipelineStepName;
  is_completed?: boolean;
  error?: string | null;
  steps: PipelineStepLog[];
}

/** POST /pipeline/start|resume/{project_id}: `_RunPlan.response`. */
export interface PipelineRunResponse {
  project_id: string;
  status: 'started' | 'resumed';
  selected_steps: PipelineStepName[];
  output_aspect_ratios: string[];
  watermark_enabled: boolean;
  credits_deducted: number;
  is_pro: boolean;
}

/** GET /clips/progress/{project_id}: YouTubeService progress or IDLE_DOWNLOAD_PROGRESS. */
export interface DownloadProgress {
  status: 'idle' | 'pending' | 'downloading' | 'uploading' | 'finalizing' | 'done' | 'error';
  percent?: number;
  /** Human size, "1.9 GB". */
  total?: string | null;
  speed?: string | null;
  eta?: string | null;
  message?: string;
}

/** backend/subscription/schema.py CreditLedgerResponse. Deductions are negative. */
export interface CreditLedgerEntry {
  id: string;
  user_id: string;
  amount: number;
  balance_after: number;
  reason: string;
  reference_id: string | null;
  reference_type: string | null;
  created_at: string;
}

/** What one project's runs cost, summed from the caller's credit ledger. */
export interface ProjectCredits {
  charged: number;
  returned: number;
}

/** The backend's message for a run the user stopped (`_mark_pipeline_failed`). */
export const CANCELLED_ERROR = 'Pipeline cancelled by user';

export const getPipelineStatus = (projectId: string, signal?: AbortSignal) =>
  apiFetch<PipelineStatus>(`/pipeline/status/${encodeURIComponent(projectId)}`, { signal });

export const getDownloadProgress = (projectId: string, signal?: AbortSignal) =>
  apiFetch<DownloadProgress>(`/clips/progress/${encodeURIComponent(projectId)}`, { signal });

export const cancelPipeline = (projectId: string) =>
  apiFetch<{ project_id: string; status: 'cancelled' }>(`/pipeline/cancel/${encodeURIComponent(projectId)}`, { method: 'POST' });

/**
 * Runs the same steps again; completed steps are restored, not re-run.
 * NEEDS-BACKEND: the run's aspect ratios, audio and clip settings are not stored,
 * so a resume without them falls back to the backend defaults. Persist them on
 * PipelineState and reuse them when the body omits them.
 */
export const resumePipeline = (projectId: string, steps: readonly PipelineStepName[], idempotencyKey: string) =>
  apiFetch<PipelineRunResponse>(`/pipeline/resume/${encodeURIComponent(projectId)}`, {
    method: 'POST',
    body: steps.length ? { steps } : {},
    idempotencyKey,
    timeoutMs: 30_000,
  });

/** Starts making clips with the default steps and the plan's defaults; charges credits. */
export const startPipeline = (projectId: string, idempotencyKey: string) =>
  apiFetch<PipelineRunResponse>(`/pipeline/start/${encodeURIComponent(projectId)}`, {
    method: 'POST',
    body: {},
    idempotencyKey,
    timeoutMs: 30_000,
  });

const RUN_REFERENCES = new Set(['video_project', 'video_project_resume', 'video_project_refund']);

/**
 * NEEDS-BACKEND: GET /projects/{id} should carry credits charged / returned
 * (screens/01 API-9). Until then they are summed from the newest ledger rows.
 */
export async function getProjectCredits(projectId: string, signal?: AbortSignal): Promise<ProjectCredits> {
  const ledger = await apiFetch<CreditLedgerEntry[]>('/subscription/ledger', { query: { limit: 200 }, signal });
  return ledger
    .filter((entry) => entry.reference_id === projectId && RUN_REFERENCES.has(entry.reference_type ?? ''))
    .reduce<ProjectCredits>(
      (sum, entry) =>
        entry.amount < 0 ? { ...sum, charged: sum.charged - entry.amount } : { ...sum, returned: sum.returned + entry.amount },
      { charged: 0, returned: 0 },
    );
}
