import type { RenderStatus } from '@/components/ui';
import type { ProjectClip } from '@/lib/api/clips';
import { type ExportLook, lookFromEditorSettings } from '@/lib/api/export/request';
import type { ExportFrameRate, ExportQuality, ExportRenderOptions, ExportResolution } from '@/lib/api/export/types';
import { duration as timelineFrames, type Timeline } from '@/lib/editor/timeline';
import { formatBytes, formatDuration } from '@/lib/utils/videoFile';

/** What a clip needs to be exported: a subset of ProjectClip, wire names kept. */
export type ExportClip = Pick<ProjectClip, 'id' | 'project_id' | 'title' | 'duration_seconds' | 'start_time' | 'end_time' | 'poster_url' | 'editor_settings'>;

/** What the dialog exports: clips of a video project, or an editor project's server version. */
export type ExportSource =
  | {
      kind: 'clips';
      projectId: string;
      clips: readonly ExportClip[];
      /** Preselected clips; all when omitted. */ selectedIds?: readonly string[];
    }
  | {
      kind: 'editor';
      projectId: string;
      title: string;
      version: number;
      timeline: Timeline;
    };

/** `useExport` takes one clip or a full source. */
export type ExportTarget = ExportClip | ExportSource;

export const toSource = (target: ExportTarget): ExportSource =>
  'kind' in target
    ? target
    : {
        kind: 'clips',
        projectId: target.project_id,
        clips: [target],
        selectedIds: [target.id],
      };

export type ExportScope = 'one' | 'selected' | 'all';

export interface ScopeChoice {
  value: ExportScope;
  label: string;
  clips: readonly ExportClip[];
}

/** "This clip" / "Selected clips (3)" / "All 12 clips" (editor §11.1); only the choices that differ. */
export function scopeChoices(source: Extract<ExportSource, { kind: 'clips' }>): ScopeChoice[] {
  const { clips, selectedIds } = source;
  const picked = selectedIds ? clips.filter((clip) => selectedIds.includes(clip.id)) : clips;
  const choices: ScopeChoice[] = [];
  if (picked.length === 1) choices.push({ value: 'one', label: 'This clip', clips: picked });
  else if (picked.length > 1 && picked.length < clips.length)
    choices.push({
      value: 'selected',
      label: `Selected clips (${picked.length})`,
      clips: picked,
    });
  if (clips.length > 1 || choices.length === 0)
    choices.push({
      value: 'all',
      label: clips.length === 1 ? 'This clip' : `All ${clips.length} clips`,
      clips,
    });
  return choices;
}

export const clipSeconds = (clip: ExportClip): number => clip.duration_seconds ?? Math.max(0, clip.end_time - clip.start_time);

/** The look the export starts from: the first clip's saved settings, or the timeline's captions. */
export function sourceLook(source: ExportSource, clips: readonly ExportClip[]): ExportLook {
  if (source.kind === 'clips') return lookFromEditorSettings(clips[0]?.editor_settings);
  return { burn_subtitles: source.timeline.captions?.enabled ?? true };
}

export function sourceSeconds(source: ExportSource, clips: readonly ExportClip[]): number {
  if (source.kind === 'editor') return timelineFrames(source.timeline) / source.timeline.fps;
  return clips.reduce((total, clip) => total + clipSeconds(clip), 0);
}

/** Width over height of the output. */
export function sourceRatio(source: ExportSource, look: ExportLook): number {
  if (source.kind === 'editor') return source.timeline.width / source.timeline.height;
  const [w, h] = (look.aspect_ratio ?? '9:16').split(':').map(Number);
  return w && h ? w / h : 9 / 16;
}

/** The ratio label for the dialog description: 9:16, 4:5, 1:1 or 16:9. */
export const ratioLabel = (ratio: number): string => (ratio < 0.7 ? '9:16' : ratio < 0.9 ? '4:5' : ratio <= 1.1 ? '1:1' : '16:9');

/** RenderCard poster shape. */
export const cardAspect = (ratio: number): '9:16' | '1:1' | '16:9' => (ratio < 0.7 ? '9:16' : ratio <= 1.3 ? '1:1' : '16:9');

/** Output pixels: the short side is the resolution (1080p 9:16 → 1080×1920), both sides even. */
export function outputSize(ratio: number, resolution: ExportResolution): { width: number; height: number } {
  const short = Number(resolution);
  const long = Math.round((short * Math.max(ratio, 1 / ratio)) / 2) * 2;
  return ratio < 1 ? { width: short, height: long } : { width: long, height: short };
}

/**
 * Typical bitrate (kbit/s) of the burn-in encode (libx264 CRF, AAC 128k) per resolution. The real
 * size depends on the footage, so the dialog says "about". NEEDS-BACKEND: EB-24 `result.size_bytes`.
 */
const TYPICAL_KBPS: Record<ExportResolution, number> = {
  '720': 4_000,
  '1080': 8_000,
  '2160': 30_000,
};
const AUDIO_KBPS = 128;

export const estimateBytes = (seconds: number, resolution: ExportResolution): number => (seconds * (TYPICAL_KBPS[resolution] + AUDIO_KBPS) * 1000) / 8;

export const DEFAULT_RENDER: ExportRenderOptions = {
  resolution: '1080',
  frame_rate: 'source',
  quality: 'high',
  format: 'mp4',
};

/**
 * The choices the server honours today: the blocking route renders 1080p MP4 at the source rate.
 * NEEDS-BACKEND: EB-24 (render options on `POST /exports`); 4K also needs a plan capability.
 */
export const HONOURED: {
  resolution: readonly ExportResolution[];
  frame_rate: readonly ExportFrameRate[];
  quality: readonly ExportQuality[];
} = {
  resolution: ['1080'],
  frame_rate: ['source'],
  quality: ['high'],
};

export const FRAME_RATE_LABEL: Record<ExportFrameRate, string> = {
  source: 'Same as source',
  '30': '30 fps',
  '60': '60 fps',
};
export const QUALITY_LABEL: Record<ExportQuality, string> = {
  standard: 'Standard',
  high: 'High',
};

/** "0:44 · 1080×1920 · MP4 · ≈ 38 MB" for one file; "3 videos · 2:10 · ZIP · ≈ 120 MB" for a bundle. */
export function renderMeta(seconds: number, files: number, size: { width: number; height: number }, resolution: ExportResolution): string {
  const bytes = `≈ ${formatBytes(estimateBytes(seconds, resolution))}`;
  return files > 1
    ? `${files} videos · ${formatDuration(seconds)} · ZIP · ${bytes}`
    : `${formatDuration(seconds)} · ${size.width}×${size.height} · MP4 · ${bytes}`;
}

export const isWorking = (status: RenderStatus): boolean => status === 'queued' || status === 'rendering' || status === 'checking';

/** A file name without characters browsers reject. */
export const fileName = (title: string, ext: 'mp4' | 'zip'): string => `${title.replace(/[\\/:*?"<>|]+/g, '').replace(/\s+/g, '_') || 'clipnera'}.${ext}`;
