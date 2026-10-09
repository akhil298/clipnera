import type { ClipEditorSettings } from '@/lib/api/clips';
import type { CaptionConfig, HookTransitionConfig } from '@/lib/types';
import { DEFAULT_CAPTION_PRESET, normalizeCaptionConfig } from '@/lib/utils/captionStyles';

import { apiFetch } from '../client';
import type { ExportLookOptions, SocialExportRequest, SocialExportResponse } from './types';

/**
 * The single home of the export request mapping (was duplicated in lib/api.ts `exportProject`,
 * lib/api/clips.ts `exportClip` and lib/api/projects.ts `exportProjectBundle`). Switch to
 * `socialExportRequest` + `exportVideoProject`.
 */

/** A clip's saved look: caption style, hook transition, aspect ratio and toggles. */
export interface ExportLook extends Partial<ExportLookOptions> {
  aspect_ratio?: string | null;
  caption_config?: Partial<CaptionConfig> | null;
  hook_transition?: HookTransitionConfig | null;
}

export interface SocialExportInput {
  /** Exactly these clips; omitted exports the top-scored `max_clips`. */
  clip_ids?: readonly string[];
  max_clips?: number;
  bundle?: boolean;
  look?: ExportLook;
}

/** SocialExportRequest `custom_config` for a caption look. */
export function captionCustomConfig(config: CaptionConfig): Record<string, unknown> {
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

/** The look a clip's saved editor settings describe; unset toggles keep the server defaults. */
export function lookFromEditorSettings(settings: ClipEditorSettings | null | undefined): ExportLook {
  return {
    aspect_ratio: settings?.aspect_ratio,
    caption_config: settings?.caption_config,
    hook_transition: settings?.hook_transition,
    burn_subtitles: settings?.captions_enabled ?? undefined,
    show_title: settings?.title_enabled ?? undefined,
    watermark_enabled: settings?.watermark_enabled ?? undefined,
  };
}

/** Builds SocialExportRequest exactly as the legacy studio export did (TikTok preset size, saved look). */
export function socialExportRequest({ clip_ids, max_clips, bundle = false, look = {} }: SocialExportInput): SocialExportRequest {
  const caption = look.caption_config ? normalizeCaptionConfig(look.caption_config) : null;
  return {
    platforms: ['tiktok'],
    ...(clip_ids?.length ? { clip_ids: [...clip_ids] } : {}),
    ...(look.aspect_ratio ? { aspect_ratio: look.aspect_ratio } : {}),
    max_clips: max_clips ?? clip_ids?.length,
    burn_subtitles: look.burn_subtitles ?? true,
    show_title: look.show_title ?? true,
    enable_emoji: caption?.emojisEnabled ?? true,
    watermark_enabled: look.watermark_enabled ?? true,
    channel_intro: look.channel_intro ?? true,
    ...(look.hook_transition ? { hook_transition: look.hook_transition } : {}),
    bundle,
    style_type: caption?.preset || DEFAULT_CAPTION_PRESET,
    ...(caption ? { custom_config: captionCustomConfig(caption) } : {}),
  };
}

/**
 * `POST /pipeline/export/{project_id}`: blocks until every render is done and verified.
 * NEEDS-BACKEND: EB-24 replaces it with `POST /exports` → Job; EB-16 adds the envelope.
 */
export const exportVideoProject = (projectId: string, body: SocialExportRequest, signal?: AbortSignal) =>
  apiFetch<SocialExportResponse>(`/pipeline/export/${encodeURIComponent(projectId)}`, {
    method: 'POST',
    body,
    signal,
    timeoutMs: 300_000,
  });
