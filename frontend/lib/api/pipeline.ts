import type { CreatorIntro } from '@/lib/api';

import { apiFetch } from './client';
import type { Entitlements } from './credits';
import { isApiError } from './errors';
import { getDownloadProgress, type PipelineRunResponse } from './jobs';

/**
 * Starting a clip run (`POST /pipeline/start/{project_id}`). The route takes a
 * plain dict (backend/pipeline/service.py `_plan_run`), so these types mirror
 * the keys it reads, not a Pydantic model:
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

/** Charges credits and queues the run. 409 VIDEO_NOT_READY until the source video is in. */
export const startClipRun = (projectId: string, body: ClipRunRequest, idempotencyKey: string) =>
  apiFetch<PipelineRunResponse>(`/pipeline/start/${encodeURIComponent(projectId)}`, {
    method: 'POST',
    body,
    idempotencyKey,
    timeoutMs: 30_000,
  });

const READY_POLL_MS = 1500;
const READY_WAIT_MS = 30 * 60_000;

function pause(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException('Stopped', 'AbortError'));
    }, { once: true });
  });
}

/**
 * Waits for the source video (YouTube download or finished upload) and then
 * starts the run. Needs this tab open until the start lands.
 * NEEDS-BACKEND: `on_ready: {pipeline}` on POST /uploads and POST /imports/youtube (screens/01 §9),
 * so the server starts the run itself and closing the tab is safe.
 */
export async function startClipRunWhenReady(projectId: string, body: ClipRunRequest, signal?: AbortSignal): Promise<PipelineRunResponse> {
  const idempotencyKey = crypto.randomUUID();
  const deadline = Date.now() + READY_WAIT_MS;
  while (Date.now() < deadline) {
    const progress = await getDownloadProgress(projectId, signal);
    if (progress.status === 'error') throw new Error(progress.message || 'The video could not be read.');
    // `idle`: the server no longer tracks the transfer (finished earlier, or restarted). Ask, and let it say.
    if (progress.status === 'done' || progress.status === 'idle') {
      try {
        return await startClipRun(projectId, body, idempotencyKey);
      } catch (err) {
        if (!(isApiError(err) && err.code === 'VIDEO_NOT_READY')) throw err;
      }
    }
    await pause(READY_POLL_MS, signal);
  }
  throw new Error('The video took too long to arrive.');
}

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
