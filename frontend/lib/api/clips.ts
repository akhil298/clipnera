import type { CaptionConfig, HookTransitionConfig } from '@/lib/types';
import { DEFAULT_CAPTION_PRESET, normalizeCaptionConfig } from '@/lib/utils/captionStyles';

import { apiFetch } from './client';
import { ApiError } from './errors';

/**
 * Typed wrappers for a project's clips. Shapes mirror the dicts built in
 * backend/clip/service.py (`list_projects_with_clips`) and
 * backend/clip_generation/service.py (`_serialize_clip`), and the Pydantic
 * models in backend/clip_generation/schema.py.
 */

/** backend/clip/model.py ProjectStatus. */
export type ProjectStatus = 'pending' | 'processing' | 'uploaded' | 'completed' | 'failed';

/** A clip as GET /clips/projects lists it. */
export interface ProjectClipSummary {
  id: string;
  title: string | null;
  score: number | null;
  duration_seconds: number | null;
  start_time: number;
  end_time: number;
  content_category: string | null;
  status: string | null;
  poster_url: string | null;
  created_at: string | null;
}

/** One row of GET /clips/projects. */
export interface ProjectRecord {
  id: string;
  title: string;
  source_type: 'youtube' | 'upload' | string;
  source_url: string | null;
  status: ProjectStatus;
  duration_seconds: number;
  created_at: string | null;
  clips: ProjectClipSummary[];
}

/** clip_generation/schema.py TranscriptEdits. */
export interface TranscriptEdits {
  removed: number[];
  highlighted: number[];
}

/** clip_generation/schema.py ClipEditorSettings; every field is omitted until set. */
export interface ClipEditorSettings {
  aspect_ratio?: string | null;
  caption_config?: Partial<CaptionConfig> | null;
  hook_transition?: HookTransitionConfig | null;
  watermark_enabled?: boolean | null;
  captions_enabled?: boolean | null;
  title_enabled?: boolean | null;
  transcript_edits?: TranscriptEdits | null;
}

/** One word of `_clip_captions`: clip-relative times, the hook teaser first. */
export interface ClipCaptionWord {
  text: string;
  start: number;
  end: number;
  source_start?: number;
  emphasis?: boolean;
  emoji?: string | null;
  speaker?: string | null;
}

/** A clip as `_serialize_clip` returns it. Heavy analysis blobs stay `unknown` here. */
export interface ProjectClip {
  id: string;
  clip_id: string;
  video_id: string;
  project_id: string;
  user_id: string;
  title: string | null;
  description: string | null;
  start_time: number;
  end_time: number;
  duration_seconds: number | null;
  hook_start: number | null;
  hook_end: number | null;
  edit_spans: unknown;
  timestamps: { start: number; end: number; duration: number | null };
  reason: string;
  score: number | null;
  scores: Record<string, number>;
  content_category: string | null;
  presigned_url: string | null;
  poster_url: string | null;
  local_path: string | null;
  status: string | null;
  subtitle_style_id: string | null;
  burned_subtitle_path: string | null;
  burned_presigned_url: string | null;
  transcript: unknown;
  captions: ClipCaptionWord[];
  visual_analysis: unknown;
  bounding_boxes: unknown;
  crop_tracking: unknown;
  output_formats: unknown;
  output_files: Record<string, string>;
  analysis_json: { clip?: { content_format?: string; reason?: string } & Record<string, unknown> } & Record<string, unknown>;
  editor_settings: ClipEditorSettings | null;
  created_at: string | null;
}

/** GET /clips/{project_id}. */
export interface ProjectClipsResponse {
  project_id: string;
  clips: ProjectClip[];
  total: number;
}

/** clip_generation/schema.py SocialExportClipResponse (hook_transition left out: unused here). */
export interface SocialExportClip {
  clip_id: string;
  platform: string;
  aspect_ratio: string;
  burned_presigned_url: string | null;
  local_path: string | null;
  s3_key: string | null;
}

/** clip_generation/schema.py SocialExportResponse. */
export interface SocialExportResponse {
  project_id: string;
  exported_clips: SocialExportClip[];
  platforms: string[];
  total_exported: number;
  watermark_enabled: boolean;
  channel_intro: boolean;
  bundle_presigned_url: string | null;
}

/**
 * NEEDS-BACKEND: GET /projects/{id} (screens/01 API-9). Until it exists the
 * project comes from the caller's list. Replace with lib/api/projects.ts once
 * the Projects builder ships it. A missing project throws a 404 ApiError.
 */
export async function getProject(projectId: string, signal?: AbortSignal): Promise<ProjectRecord> {
  const { projects } = await apiFetch<{ projects: ProjectRecord[]; total: number }>('/clips/projects', { signal });
  const project = projects.find((item) => item.id === projectId);
  if (!project) {
    throw new ApiError({ status: 404, code: 'NOT_FOUND', message: 'Project not found', requestId: crypto.randomUUID() });
  }
  return project;
}

export const listProjectClips = (projectId: string, signal?: AbortSignal) =>
  apiFetch<ProjectClipsResponse>(`/clips/${encodeURIComponent(projectId)}`, { signal });

/** NEEDS-BACKEND: DELETE /clips/item/{clip_id} does not exist yet; this call fails until it does. */
export const deleteClip = (clipId: string) =>
  apiFetch<null>(`/clips/item/${encodeURIComponent(clipId)}`, { method: 'DELETE' });

/** The SocialExportRequest `custom_config` for a caption look (same mapping as lib/api.ts exportProject). */
function captionCustomConfig(config: CaptionConfig) {
  return {
    font_size: config.fontSize,
    font_family: config.fontFamily,
    font_color: config.textColor,
    highlight_color: config.highlightColor,
    secondary_highlight_color: config.secondaryHighlightColor,
    has_bg_box: config.hasBgBox,
    bg_box_color: config.bgBoxColor,
    word_box_color: config.wordBoxColor,
    uppercase: config.uppercase,
    animation: config.animation,
    animation_speed: config.animationSpeed,
    position_y: config.positionY,
    emojis_enabled: config.emojisEnabled,
    emoji_collection: config.emojiCollection,
    max_words_per_line: config.maxWordsPerLine,
    shadow_intensity: config.shadowIntensity,
    title_font_size: config.titleFontSize,
    title_position_y: config.titlePositionY,
  };
}

/**
 * Renders one clip with its own saved look (caption style, size, hook
 * transition, toggles) and returns a URL that saves the file. The raw cut has
 * no captions or title, so it is never what Download hands over.
 */
export async function exportClip(clip: ProjectClip): Promise<string> {
  const settings = clip.editor_settings ?? {};
  const caption = normalizeCaptionConfig(settings.caption_config ?? undefined);
  const result = await apiFetch<SocialExportResponse>(`/pipeline/export/${encodeURIComponent(clip.project_id)}`, {
    method: 'POST',
    timeoutMs: 180_000,
    body: {
      platforms: ['tiktok'],
      clip_ids: [clip.id],
      aspect_ratio: settings.aspect_ratio ?? '9:16',
      burn_subtitles: settings.captions_enabled ?? true,
      show_title: settings.title_enabled ?? true,
      watermark_enabled: settings.watermark_enabled ?? true,
      enable_emoji: caption.emojisEnabled,
      style_type: caption.preset || DEFAULT_CAPTION_PRESET,
      custom_config: captionCustomConfig(caption),
      ...(settings.hook_transition ? { hook_transition: settings.hook_transition } : {}),
    },
  });
  const url = result.exported_clips.find((item) => item.clip_id === clip.id)?.burned_presigned_url;
  if (!url) {
    throw new ApiError({ status: 200, code: 'EXPORT_EMPTY', message: 'The render finished without a file to download.', requestId: crypto.randomUUID() });
  }
  return url;
}
