import type { DownloadProgress, EntitlementsResponse, YouTubeMetadataResponse } from '@/lib/api';
import { DEFAULT_PIPELINE_STEPS } from '@/lib/api';
import type { PipelineStep } from '@/lib/types';

import { apiFetch } from './client';
import { isApiError } from './errors';

/**
 * Home's calls. Every one is a route the legacy dashboard already uses, so a
 * project made here is the same project the old UI makes.
 */

/** `GET /me` (backend/user/schema.py UserProfileResponse); Home only reads these fields. */
export interface HomeUser {
  id: string;
  name: string;
}

/** One clip row in `GET /clips/projects` (backend/clip/service.py list_projects_with_clips). */
export interface HomeProjectClip {
  id: string;
  title: string;
  score: number | null;
  duration_seconds: number | null;
  start_time: number | null;
  end_time: number | null;
  content_category: string | null;
  status: string;
  poster_url: string | null;
  created_at: string | null;
}

/** `ProjectStatus` in backend/clip/model.py. */
export type HomeProjectStatus = 'pending' | 'processing' | 'uploaded' | 'completed' | 'failed';

export interface HomeProject {
  id: string;
  title: string;
  source_type: string;
  source_url: string | null;
  status: HomeProjectStatus;
  duration_seconds: number;
  created_at: string | null;
  clips: HomeProjectClip[];
}

export interface HomeProjectList {
  projects: HomeProject[];
  total: number;
}

/** One entry of `POST /pipeline/status/batch` (backend/pipeline/service.py _status_payload / _not_started). */
export interface PipelineRunStatus {
  project_id: string;
  status: 'not_started' | 'pending' | 'running' | 'completed' | 'error';
  current_step?: string | null;
  is_completed?: boolean;
  error?: string | null;
  steps: PipelineStep[];
}

/** `POST /clips/download` (backend/clip/schema.py VideoMetadataResponse). */
export interface CreatedYoutubeProject {
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
}

/** The `clip_settings` keys of `POST /pipeline/start` that Home sets (read in backend/content_intelligence). */
export interface HomeClipSettings {
  caption_script: 'auto';
  broll: boolean;
  min_clip_duration?: number;
  max_clip_duration?: number;
}

/** `POST /pipeline/start/{id}` answer (backend/pipeline/service.py start). */
export interface PipelineStartResult {
  project_id: string;
  status: string;
  selected_steps: string[];
  credits_deducted: number;
}

/** `POST /editor/projects` answer (backend/editor/schema.py EditorProjectSummary, timeline omitted). */
export interface CreatedEditorProject {
  id: string;
  title: string;
}

/** The upload flow's defaults for Studio voice and formats (components/dashboard/UploadModal.tsx). */
const DEFAULT_AUDIO_CONFIG = {
  aiDenoise: true,
  noiseSuppressionStrength: 90,
  deReverb: true,
  vocalClarityEq: true,
  humFilter: true,
};
const DEFAULT_RATIOS = ['9:16'];
const DOWNLOAD_POLL_MS = 1500;
const DOWNLOAD_WAIT_MS = 30 * 60_000;

export const homeApi = {
  me: (signal?: AbortSignal) => apiFetch<HomeUser>('/me', { signal }),
  entitlements: (signal?: AbortSignal) => apiFetch<EntitlementsResponse>('/subscription/entitlements', { signal }),
  projects: (signal?: AbortSignal) => apiFetch<HomeProjectList>('/clips/projects', { signal }),
  runStatuses: (projectIds: string[], signal?: AbortSignal) =>
    apiFetch<{ statuses: Record<string, PipelineRunStatus> }>('/pipeline/status/batch', {
      method: 'POST',
      body: { project_ids: projectIds },
      signal,
    }),
  youtubeMetadata: (url: string, signal?: AbortSignal) =>
    apiFetch<YouTubeMetadataResponse>('/clips/youtube/metadata', { method: 'POST', body: { url }, signal, timeoutMs: 30_000 }),
  createFromYoutube: (url: string, idempotencyKey: string) =>
    apiFetch<CreatedYoutubeProject>('/clips/download', { method: 'POST', body: { url }, idempotencyKey, timeoutMs: 60_000 }),
  downloadProgress: (projectId: string) => apiFetch<DownloadProgress>(`/clips/progress/${projectId}`),
  startClips: (projectId: string, clipSettings: HomeClipSettings, idempotencyKey: string) =>
    apiFetch<PipelineStartResult>(`/pipeline/start/${projectId}`, {
      method: 'POST',
      body: {
        steps: DEFAULT_PIPELINE_STEPS,
        audio_config: DEFAULT_AUDIO_CONFIG,
        output_aspect_ratios: DEFAULT_RATIOS,
        clip_settings: clipSettings,
      },
      idempotencyKey,
    }),
  createEmptyEdit: () =>
    apiFetch<CreatedEditorProject>('/editor/projects', { method: 'POST', body: { title: 'Untitled project', aspect: '9:16' } }),
};

/**
 * `POST /pipeline/start` refuses with 409 VIDEO_NOT_READY until the download
 * lands, so the run starts once `/clips/progress` says done — the same handoff
 * as `startPipelineWhenReady` in lib/api.ts. It is not tied to a component:
 * it keeps going after Home navigates to the project page.
 * NEEDS-BACKEND: POST /imports/youtube with `on_ready.pipeline` (screens/01 §9), so this survives a closed tab.
 */
export async function startClipsWhenReady(projectId: string, clipSettings: HomeClipSettings): Promise<PipelineStartResult> {
  const idempotencyKey = crypto.randomUUID();
  const deadline = Date.now() + DOWNLOAD_WAIT_MS;
  while (Date.now() < deadline) {
    const progress = await homeApi.downloadProgress(projectId);
    if (progress.status === 'error') throw new Error(progress.message || 'The video could not be fetched from YouTube.');
    // `idle` means the server no longer tracks the download (finished earlier, or restarted): ask to start and let it say.
    if (progress.status === 'done' || progress.status === 'idle') {
      try {
        return await homeApi.startClips(projectId, clipSettings, idempotencyKey);
      } catch (err) {
        if (!(isApiError(err) && err.code === 'VIDEO_NOT_READY')) throw err;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, DOWNLOAD_POLL_MS));
  }
  throw new Error('The video took too long to arrive.');
}
