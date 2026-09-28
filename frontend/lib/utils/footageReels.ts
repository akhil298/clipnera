import type { EditResolvedScriptMode, EditScriptMode, EditStatus } from '@/lib/api';
import type { StatusTone } from '@/components/ui/StatusPill';

/** Mirrors reel_credits() in backend/edit_engine/pricing.py and its settings. */
export const EDIT_BASE_CREDITS = 6;
export const EDIT_OUTPUT_SECONDS_PER_CREDIT = 3;
export const EDIT_OPUS_CREDIT_MULTIPLIER = 1.5;

export const estimateEditCredits = (outputSeconds: number, rawSeconds: number, opus: boolean): number => {
  const credits = EDIT_BASE_CREDITS + Math.ceil(Math.max(0, outputSeconds) / EDIT_OUTPUT_SECONDS_PER_CREDIT)
    + Math.ceil(Math.max(0, rawSeconds) / 60);
  return opus ? Math.ceil(credits * EDIT_OPUS_CREDIT_MULTIPLIER) : credits;
};

export const EDIT_STATUS: Record<EditStatus, { tone: StatusTone; label: string }> = {
  draft: { tone: 'neutral', label: 'Draft' },
  analyzing: { tone: 'processing', label: 'Planning' },
  planned: { tone: 'scheduled', label: 'Plan ready' },
  rendering: { tone: 'processing', label: 'Rendering' },
  done: { tone: 'ready', label: 'Done' },
  failed: { tone: 'failed', label: 'Failed' },
};

export const SCRIPT_MODE_OPTIONS: [EditScriptMode, string][] = [
  ['auto', 'Decide for me'],
  ['spoken', 'I say this in the video'],
  ['voiceover', 'Read it as a voiceover'],
  ['onscreen', 'Show it as on-screen text'],
  ['direction', 'Just use it as direction'],
];

export const RESOLVED_SCRIPT_LABEL: Record<EditResolvedScriptMode, string> = {
  none: 'No script: the story comes from your footage',
  spoken: 'Following your script',
  voiceover: 'Your script is the voiceover',
  onscreen: 'Your script is on screen',
  direction: 'Your script is used as direction',
};

export const CONTENT_TYPE_LABEL: Record<string, string> = {
  talking_head: 'Talking head',
  montage: 'Montage',
  vlog: 'Vlog',
};

/** The progress steps the analysis reports, in order (see backend edit_engine/jobs.py). */
export const ANALYSIS_STEPS = [
  'Reading your clips',
  'Listening to what you said',
  'Finding the best takes',
  'Planning the edit',
];

export const TARGET_OPTIONS = [0, 15, 30, 45, 60, 90] as const;

/** Browser-side duration of a video or audio file, so over-limit footage is refused before upload. */
export const mediaDuration = (file: File): Promise<number | null> =>
  new Promise((resolve) => {
    if (!file.type.startsWith('video/') && !file.type.startsWith('audio/')) {
      resolve(null);
      return;
    }
    const url = URL.createObjectURL(file);
    const media = document.createElement(file.type.startsWith('video/') ? 'video' : 'audio');
    media.preload = 'metadata';
    const done = (value: number | null) => {
      URL.revokeObjectURL(url);
      resolve(value);
    };
    media.onloadedmetadata = () => done(Number.isFinite(media.duration) ? media.duration : null);
    media.onerror = () => done(null);
    media.src = url;
  });

export const formatSeconds = (s: number): string =>
  `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
