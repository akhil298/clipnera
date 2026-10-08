import type { ProjectSummary } from '@/lib/api/projects';
import { CANCELLED_ERROR, type DownloadProgress, type PipelineStatus, type PipelineStepLog, type PipelineStepName } from '@/lib/api/jobs';
import type { ProgressStepStatus } from '@/components/ui/ProgressSteps';
import type { RunStep } from '@/components/ui/StepList';
import { formatTimecode } from '@/lib/design/timecode';
import { finished, stepWords } from '@/lib/projects/run';

/**
 * Pure read model for the project page: which phase the project is in, the
 * five stages people see, and the detailed steps in plain words
 * (screens/01 §10 stage mapping). No React here, so it stays easy to test.
 */

export type Phase = 'importing' | 'not_started' | 'running' | 'failed' | 'stopped' | 'done';

export function phaseOf(project: Pick<ProjectSummary, 'status'>, status: PipelineStatus | undefined): Phase {
  if (project.status === 'pending') return 'importing';
  if (!status || status.status === 'not_started') {
    if (project.status === 'completed') return 'done';
    if (project.status === 'failed') return 'failed';
    return project.status === 'processing' ? 'running' : 'not_started';
  }
  if (status.status === 'error') return status.error === CANCELLED_ERROR ? 'stopped' : 'failed';
  if (status.status === 'completed' || status.is_completed) return 'done';
  return 'running';
}

export const isLive = (phase: Phase) => phase === 'importing' || phase === 'running';

/** The five stages, and which server steps each one covers. */
export const STAGES = [
  { id: 'import', label: 'Getting your video', steps: ['download', 'audio_extraction'] },
  { id: 'audio', label: 'Cleaning up the audio', steps: ['ai_noise_cancellation'] },
  { id: 'transcribe', label: 'Transcribing', steps: ['transcription'] },
  {
    id: 'moments',
    label: 'Finding the best moments',
    steps: ['topic_research', 'visual_analysis', 'content_classification', 'highlight_detection', 'bounding_box_detection', 'scoring'],
  },
  {
    id: 'clips',
    label: 'Making your clips',
    steps: ['metadata_generation', 'aspect_ratio_render', 'clip_generation', 'subtitle_styling', 'burn_in_export', 'depth_captions'],
  },
] as const satisfies ReadonlyArray<{ id: string; label: string; steps: readonly PipelineStepName[] }>;

export type StageId = (typeof STAGES)[number]['id'];

export interface StageView {
  id: StageId;
  label: string;
  status: ProgressStepStatus;
  /** The step running inside this stage, when there is one. */
  running?: PipelineStepLog;
  failed?: PipelineStepLog;
  /** Steps of this run inside the stage. */
  logs: PipelineStepLog[];
}

/**
 * Stage status from its steps. The import stage is also done once the source
 * has arrived (the download happens before the run's own steps). Stages with
 * no steps in this run (audio clean-up switched off) are left out.
 */
export function stagesOf(phase: Phase, steps: readonly PipelineStepLog[]): StageView[] {
  return STAGES.flatMap((stage): StageView[] => {
    const logs = steps.filter((log) => (stage.steps as readonly string[]).includes(log.step));
    const running = logs.find((log) => log.status === 'running');
    const failed = logs.find((log) => log.status === 'failed');
    const base = { id: stage.id, label: stage.label, logs, running, failed };
    if (stage.id === 'import') {
      if (phase === 'importing') return [{ ...base, status: 'active' }];
      if (failed) return [{ ...base, status: 'failed' }];
      return [{ ...base, status: running ? 'active' : 'done' }];
    }
    if (logs.length === 0) return phase === 'done' || phase === 'importing' || phase === 'not_started' ? [] : [{ ...base, status: 'upcoming' }];
    if (failed) return [{ ...base, status: 'failed' }];
    if (logs.every(finished)) return [{ ...base, status: 'done' }];
    if (running || logs.some(finished)) return [{ ...base, status: phase === 'running' ? 'active' : running ? 'failed' : 'upcoming' }];
    return [{ ...base, status: 'upcoming' }];
  });
}

/** Backend timestamps are naive UTC (`datetime.utcnow().isoformat()`). */
export function parseUtc(value: string | null | undefined): number | null {
  if (!value) return null;
  const time = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isFinite(time) ? time : null;
}

function seconds(log: PipelineStepLog): number | null {
  const start = parseUtc(log.started_at);
  const end = parseUtc(log.finished_at);
  return start !== null && end !== null ? Math.max(0, (end - start) / 1000) : null;
}

/** Wall time of the run so far (or in total, once it ended). */
export function elapsedSeconds(steps: readonly PipelineStepLog[], now: number): number | null {
  const starts = steps.map((log) => parseUtc(log.started_at)).filter((time): time is number => time !== null);
  if (starts.length === 0) return null;
  const running = steps.some((log) => log.status === 'running');
  const ends = steps.map((log) => parseUtc(log.finished_at)).filter((time): time is number => time !== null);
  const end = running || ends.length === 0 ? now : Math.max(...ends);
  return Math.max(0, (end - Math.min(...starts)) / 1000);
}

/** The detailed list behind the disclosure: plain words, past tense once done, real durations. */
export function runSteps(steps: readonly PipelineStepLog[]): RunStep[] {
  return steps.map((log): RunStep => {
    const took = seconds(log);
    switch (log.status) {
      case 'completed':
        return { id: log.step, label: stepWords(log.step, true), status: 'done', detail: took !== null ? `Took ${formatTimecode(took)}` : undefined };
      case 'skipped':
        return { id: log.step, label: stepWords(log.step), status: 'skipped', detail: log.message ?? 'Not needed for this video' };
      case 'running':
        return {
          id: log.step,
          label: stepWords(log.step),
          status: 'active',
          progress: log.progress_percent > 0 ? `${Math.round(log.progress_percent)}%` : undefined,
        };
      case 'failed':
        return { id: log.step, label: stepWords(log.step), status: 'failed', detail: log.message ?? undefined };
      default:
        return { id: log.step, label: stepWords(log.step), status: 'queued' };
    }
  });
}

/** "Uploading · 1.2 GB · 62%" from the source download's own progress. */
export function importLine(progress: DownloadProgress | undefined, sourceType: string): string {
  const from = sourceType === 'upload' ? 'Receiving your upload' : 'Downloading from YouTube';
  if (!progress || progress.status === 'idle' || progress.status === 'pending') return from;
  if (progress.status === 'uploading' || progress.status === 'finalizing') return 'Saving the video';
  const size = progress.total ? ` · ${progress.total}` : '';
  return `${from}${size}`;
}
