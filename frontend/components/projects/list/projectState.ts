import type { BadgeTone } from '@/components/ui';
import type { PipelineRunStatus, ProjectSummary } from '@/lib/api/projects';
import { youtubeThumbnailUrl } from '@/lib/utils/urlParser';

/** What a project card shows. Derived from the project row plus its latest run. */
export type ProjectKind = 'running' | 'ready' | 'failed' | 'stopped' | 'idle';

export interface ProjectView {
  project: ProjectSummary;
  kind: ProjectKind;
  /** Badge text: "Transcribing · step 4 of 12", "Ready", "Failed". */
  label: string;
  tone: BadgeTone;
  poster: string | undefined;
  /** "YouTube" or "Upload". */
  source: string;
  clipCount: number;
  href: string;
}

/** Plain words for each `PipelineStepType` (backend/pipeline/model.py). */
const STEP_LABEL: Record<string, string> = {
  download: 'Getting the video',
  audio_extraction: 'Pulling the audio',
  ai_noise_cancellation: 'Cleaning the audio',
  transcription: 'Transcribing',
  topic_research: 'Reading the topic',
  visual_analysis: 'Watching the video',
  content_classification: 'Sorting the content',
  highlight_detection: 'Finding the best moments',
  bounding_box_detection: 'Tracking faces',
  scoring: 'Scoring moments',
  metadata_generation: 'Writing titles',
  aspect_ratio_render: 'Reframing',
  clip_generation: 'Cutting clips',
  subtitle_styling: 'Styling captions',
  burn_in_export: 'Rendering clips',
  depth_captions: 'Placing captions',
};

const CANCELLED = /cancel/i;

function runningLabel(run: PipelineRunStatus | undefined): string {
  if (!run || run.status === 'not_started' || run.steps.length === 0) return 'Getting the video';
  const done = run.steps.filter((step) => step.status === 'completed' || step.status === 'skipped').length;
  const step = (run.current_step && STEP_LABEL[run.current_step]) || 'Starting';
  return `${step} · step ${Math.min(done + 1, run.steps.length)} of ${run.steps.length}`;
}

function kindOf(project: ProjectSummary, run: PipelineRunStatus | undefined): ProjectKind {
  if (run && run.status !== 'not_started') {
    if (run.error) return CANCELLED.test(run.error) ? 'stopped' : 'failed';
    if (run.is_completed) return 'ready';
    return 'running';
  }
  if (project.status === 'failed') return 'failed';
  if (project.clips.length > 0 || project.status === 'completed') return 'ready';
  if (project.status === 'pending' || project.status === 'processing') return 'running';
  // Uploaded with no run: either the run state has not arrived yet, or it never started.
  return run ? 'idle' : 'running';
}

const BADGE: Record<Exclude<ProjectKind, 'running'>, { label: string; tone: BadgeTone }> = {
  ready: { label: 'Ready', tone: 'success' },
  failed: { label: 'Failed', tone: 'danger' },
  stopped: { label: 'Stopped', tone: 'neutral' },
  idle: { label: 'Not started', tone: 'neutral' },
};

export function projectView(project: ProjectSummary, run: PipelineRunStatus | undefined): ProjectView {
  const kind = kindOf(project, run);
  const badge = kind === 'running' ? { label: runningLabel(run), tone: 'accent' as const } : BADGE[kind];
  return {
    project,
    kind,
    ...badge,
    poster: project.clips.find((clip) => clip.poster_url)?.poster_url ?? (youtubeThumbnailUrl(project.source_url ?? '') || undefined),
    source: project.source_type === 'upload' ? 'Upload' : 'YouTube',
    clipCount: project.clips.length,
    href: `/dashboard/projects/${project.id}`,
  };
}

export const isRunning = (view: ProjectView) => view.kind === 'running';

/** "4 h 41 min", "38 min", "45 s". */
export function spokenLength(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const minutes = Math.round(seconds / 60);
  const hours = Math.floor(minutes / 60);
  return hours > 0 ? `${hours} h ${minutes % 60} min` : `${minutes} min`;
}

export const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;
