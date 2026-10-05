import type { PipelineStepLog, PipelineStepName } from '@/lib/api/jobs';

/**
 * Pipeline steps in plain words, and how far a run has got. Shared by the
 * project page and the header's activity indicator; no React, so it stays easy to test.
 */

const STEP_WORDS: Record<PipelineStepName, [present: string, past: string]> = {
  download: ['Getting the video', 'Got the video'],
  audio_extraction: ['Taking out the audio', 'Took out the audio'],
  ai_noise_cancellation: ['Cleaning up the audio', 'Cleaned up the audio'],
  transcription: ['Transcribing the speech', 'Transcribed the speech'],
  topic_research: ['Working out the topics', 'Worked out the topics'],
  visual_analysis: ['Looking at faces and framing', 'Looked at faces and framing'],
  content_classification: ['Sorting the kinds of moment', 'Sorted the kinds of moment'],
  highlight_detection: ['Finding the best moments', 'Found the best moments'],
  bounding_box_detection: ['Tracking the speakers', 'Tracked the speakers'],
  scoring: ['Scoring each moment', 'Scored each moment'],
  metadata_generation: ['Writing titles and hashtags', 'Wrote titles and hashtags'],
  aspect_ratio_render: ['Reframing each clip', 'Reframed each clip'],
  clip_generation: ['Cutting the clips', 'Cut the clips'],
  subtitle_styling: ['Styling the captions', 'Styled the captions'],
  burn_in_export: ['Adding captions to each clip', 'Added captions to each clip'],
  depth_captions: ['Placing depth captions', 'Placed depth captions'],
};

export const stepWords = (step: PipelineStepName, past = false): string => STEP_WORDS[step]?.[past ? 1 : 0] ?? step;

export const finished = (log: Pick<PipelineStepLog, 'status'>) => log.status === 'completed' || log.status === 'skipped';

/** Percent through the whole run, counting the running step's own percent. */
export function runPercent(steps: readonly PipelineStepLog[]): number | null {
  if (steps.length === 0) return null;
  const done = steps.filter(finished).length;
  const running = steps.find((log) => log.status === 'running');
  const partial = running ? Math.min(100, Math.max(0, running.progress_percent)) / 100 : 0;
  return Math.round(((done + partial) / steps.length) * 100);
}
