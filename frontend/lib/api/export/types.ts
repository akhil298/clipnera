import type { HookTransitionApplied, HookTransitionConfig } from '@/lib/types';

/**
 * Wire types for exports. The blocking route mirrors backend/clip_generation/schema.py
 * (SocialExportRequest, SocialExportClipResponse, SocialExportResponse); keep them in step.
 */

/** SocialExportRequest (`POST /pipeline/export/{project_id}`). */
export interface SocialExportRequest {
  platforms: string[];
  style_type?: string | null;
  custom_config?: Record<string, unknown> | null;
  /** Exactly these clips; omitted exports the top-scored `max_clips`. */
  clip_ids?: string[] | null;
  /** 9:16, 1:1, 4:5 or 16:9; overrides each platform's default ratio. */
  aspect_ratio?: string | null;
  max_clips?: number | null;
  max_duration?: number | null;
  enable_emoji?: boolean | null;
  /** Only paid plans can turn it off; the server forces it otherwise. */
  watermark_enabled: boolean;
  burn_subtitles: boolean;
  /** Applies only with `burn_subtitles`. */
  show_title: boolean;
  animation_speed?: number | null;
  /** Omitted means Auto. */
  hook_transition?: HookTransitionConfig | null;
  /** Also pack every render into one ZIP (`bundle_presigned_url`). */
  bundle: boolean;
  /** Applied only on plans with `creator_intro` once an intro is ready. */
  channel_intro: boolean;
}

/** SocialExportClipResponse. */
export interface SocialExportClip {
  clip_id: string;
  platform: string;
  aspect_ratio: string;
  burned_presigned_url: string | null;
  local_path: string | null;
  s3_key: string | null;
  hook_transition: HookTransitionApplied | null;
}

/** SocialExportResponse. The route returns it bare (no envelope); apiFetch passes it through. */
export interface SocialExportResponse {
  project_id: string;
  exported_clips: SocialExportClip[];
  platforms: string[];
  total_exported: number;
  /** The watermark actually applied: always true on plans that force it. */
  watermark_enabled: boolean;
  /** Whether the channel intro was put in front of the renders. */
  channel_intro: boolean;
  bundle_presigned_url: string | null;
}

// --- Render options (the dialog's choices) ----------------------------------

export type ExportResolution = '720' | '1080' | '2160';
export type ExportFrameRate = 'source' | '30' | '60';
export type ExportQuality = 'standard' | 'high';
export type ExportFormat = 'mp4';

export interface ExportRenderOptions {
  resolution: ExportResolution;
  frame_rate: ExportFrameRate;
  quality: ExportQuality;
  format: ExportFormat;
}

/** What the burned-in video carries, beside the render options. */
export interface ExportLookOptions {
  burn_subtitles: boolean;
  show_title: boolean;
  watermark_enabled: boolean;
  channel_intro: boolean;
}

// --- Export as a job ---------------------------------------------------------
// NEEDS-BACKEND: EB-24 — POST /exports, GET /jobs/{id}, POST /jobs/{id}/cancel. Shapes follow
// docs/revamp/screens/02-editor.md §11.3; confirm against the backend schema when it lands.

export type ExportSourceRef = { type: 'video_project'; id: string; clip_ids: string[] } | { type: 'editor_project'; id: string; version_id: number };

export interface CreateExportRequest {
  source: ExportSourceRef;
  options: ExportRenderOptions & ExportLookOptions & { bundle: boolean };
}

export type ExportJobStatus = 'queued' | 'running' | 'checking' | 'succeeded' | 'failed' | 'cancelled' | 'expired';

export interface ExportJobResponse {
  id: string;
  status: ExportJobStatus;
  /** "Burning in captions". */
  step: string | null;
  progress: { percent: number; eta_seconds: number | null } | null;
  queue_position: number | null;
  result: {
    url: string;
    size_bytes: number | null;
    share_url: string | null;
  } | null;
  error: { message: string; retryable: boolean } | null;
}
