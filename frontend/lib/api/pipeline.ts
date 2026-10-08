import type { CreatorIntro } from '@/lib/api';

import { apiFetch } from './client';
import type { Entitlements } from './credits';

/**
 * The settings of a clip run. PipelineStartRequest types its fields as plain
 * dicts (backend/pipeline/schema.py), so these types mirror the keys the run reads:
 * - `audio_config`: backend/audio/enhancement/service.py `process_audio_pipeline` (snake_case keys;
 *   the legacy UploadModal sent camelCase, which the backend ignored).
 * - `output_aspect_ratios`: clamped to the plan by `resolve_output_aspect_ratios`.
 * - `clip_settings`: `_clamp_clip_settings` plus the keys read in content_intelligence and clip_generation.
 * `steps` is left out so the backend's default run (which includes `burn_in_export`) applies.
 */

/** video_processor/geometry.py SUPPORTED_ASPECT_RATIOS, tallest first. */
export const OUTPUT_RATIOS = ['9:16', '4:5', '1:1', '16:9'] as const;
export type OutputRatio = (typeof OUTPUT_RATIOS)[number];

/** transcription/transliterate.py CAPTION_SCRIPTS. */
export type CaptionScript = 'auto' | 'roman' | 'native';

export type StudioVoiceLevel = 'light' | 'balanced' | 'maximum';

/** `noise_suppression_strength` per level (screens/01 R33). */
export const STUDIO_VOICE_STRENGTH: Record<StudioVoiceLevel, number> = { light: 55, balanced: 80, maximum: 90 };

export interface AudioConfig {
  ai_denoise: boolean;
  noise_suppression_strength: number;
  de_reverb: boolean;
  vocal_clarity_eq: boolean;
  hum_filter: boolean;
}

export interface ClipSettings {
  caption_script: CaptionScript;
  /** B-roll cutaways; charged per clip that gets them. */
  broll: boolean;
  /** Also stitch moments from across the video into story clips. */
  story_clips: boolean;
  min_clip_duration?: number;
  max_clip_duration?: number;
  /** NEEDS-BACKEND: `clip_settings.prompt` (screens/01 API-8) — stored with the run, not read by the pipeline yet. */
  prompt?: string;
}

export interface ClipRunRequest {
  audio_config: AudioConfig;
  output_aspect_ratios: OutputRatio[];
  clip_settings: ClipSettings;
}

/**
 * The run settings sent with a YouTube download or an upload's `complete`
 * (backend/pipeline/schema.py PipelineStartRequest): the server starts the run
 * itself once the video is stored, so closing the tab afterwards is safe.
 */
export type PipelineStartRequest = ClipRunRequest;

/** `POST /clips/download` answer (backend/clip/schema.py VideoMetadataResponse). */
export interface VideoDownloadResponse {
  id: string;
  title: string;
  thumbnail_url: string;
  channel_title: string;
  duration_formatted: string;
  resolution: string;
  aspect_ratio: string | number;
  file_size: number;
  presigned_url: string;
  original_url: string;
  status: string;
  created_at: string;
  /** Charged now, when the download is requested with a run; 0 otherwise. */
  credits_deducted: number;
}

/**
 * Creates the project, starts the download and charges for the run at once
 * (charge at submit); the server starts the run when the video is stored and
 * refunds the charge if it can't. 402 INSUFFICIENT_CREDITS when the balance is short.
 */
export const importYoutube = (url: string, pipeline: PipelineStartRequest, idempotencyKey: string) =>
  apiFetch<VideoDownloadResponse>('/clips/download', {
    method: 'POST',
    body: { url, pipeline },
    idempotencyKey,
    timeoutMs: 60_000,
  });

/**
 * Credits a run costs: mirrors `SubscriptionService.calculate_video_credit_cost`
 * (backend/subscription/service.py). Exact when `durationSeconds` is the
 * server's whole-second duration.
 */
export function runCreditCost(
  pricing: Pick<Entitlements, 'credits_per_video_minute' | 'extra_aspect_ratio_credit_share'>,
  durationSeconds: number,
  ratioCount: number,
): number {
  const base = (durationSeconds / 60) * pricing.credits_per_video_minute;
  const extra = Math.max(0, ratioCount - 1) * pricing.extra_aspect_ratio_credit_share;
  return Math.max(1, Math.ceil(base * (1 + extra)));
}

/** `GET /creator-intro` (backend/creator_intro/schema.py), read before a run to offer the channel intro. null until saved. */
export const getCreatorIntro = (signal?: AbortSignal) => apiFetch<CreatorIntro | null>('/creator-intro', { signal });
