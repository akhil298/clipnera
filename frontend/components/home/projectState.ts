import type { HomeProject, PipelineRunStatus } from '@/lib/api/home';
import { youtubeThumbnailUrl } from '@/lib/utils/urlParser';

export type ProjectRunState =
  | { kind: 'running'; step: string; done: number; total: number }
  | { kind: 'ready' }
  | { kind: 'failed' };

/** The 11 pipeline steps folded into the five stages a person sees (screens/01 §10). */
const STAGE_BY_STEP: Record<string, string> = {
  download: 'Getting your video',
  audio_extraction: 'Cleaning up the audio',
  ai_noise_cancellation: 'Cleaning up the audio',
  transcription: 'Transcribing',
  topic_research: 'Finding the best moments',
  visual_analysis: 'Finding the best moments',
  content_classification: 'Finding the best moments',
  highlight_detection: 'Finding the best moments',
  scoring: 'Finding the best moments',
  metadata_generation: 'Making your clips',
  aspect_ratio_render: 'Making your clips',
  clip_generation: 'Making your clips',
};

const UNFINISHED: ReadonlySet<string> = new Set(['pending', 'processing', 'uploaded']);

/** Projects whose run state the server still has to tell us. */
export const isUnfinished = (project: HomeProject): boolean => UNFINISHED.has(project.status);

/**
 * Same rule as the legacy dashboard: the pipeline's own view wins when there is
 * one; without it, the project row's status decides.
 */
export function runStateOf(project: HomeProject, run: PipelineRunStatus | undefined): ProjectRunState {
  if (project.status === 'failed' || run?.error) return { kind: 'failed' };
  const steps = run?.steps ?? [];
  if (steps.length > 0) {
    if (run?.is_completed) return { kind: 'ready' };
    const done = steps.filter((step) => step.status === 'completed' || step.status === 'skipped').length;
    const current = steps.find((step) => step.status === 'running')?.step ?? run?.current_step ?? '';
    return { kind: 'running', step: STAGE_BY_STEP[current] ?? 'Getting started', done, total: steps.length };
  }
  if (isUnfinished(project)) return { kind: 'running', step: STAGE_BY_STEP.download, done: 0, total: 0 };
  return { kind: 'ready' };
}

export const posterOf = (project: HomeProject): string | undefined =>
  project.clips.find((clip) => clip.poster_url)?.poster_url ?? (youtubeThumbnailUrl(project.source_url ?? '') || undefined);

export const projectHref = (projectId: string): string => `/dashboard/projects/${projectId}`;

/** Newest first; rows without a date sink. */
export const byNewest = (a: HomeProject, b: HomeProject): number => (b.created_at ?? '').localeCompare(a.created_at ?? '');
