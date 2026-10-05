import { LENGTH_CHOICES, type LengthChoiceId } from '@/components/home/starters';
import {
  STUDIO_VOICE_STRENGTH,
  type CaptionScript,
  type ClipRunRequest,
  type OutputRatio,
  type StudioVoiceLevel,
} from '@/lib/api/pipeline';

/** Every choice the New video flow sends; each one is read by the backend (see lib/api/pipeline.ts). */
export interface RunOptions {
  formats: OutputRatio[];
  studioVoice: boolean;
  strength: StudioVoiceLevel;
  removeEcho: boolean;
  voiceClarity: boolean;
  humFilter: boolean;
  length: LengthChoiceId | 'auto';
  storyClips: boolean;
  broll: boolean;
  captionScript: CaptionScript;
}

/** The backend's own defaults (DEFAULT_AUDIO_CONFIG, 9:16, auto script). */
export const DEFAULT_OPTIONS: RunOptions = {
  formats: ['9:16'],
  studioVoice: true,
  strength: 'maximum',
  removeEcho: true,
  voiceClarity: true,
  humFilter: true,
  length: 'auto',
  storyClips: false,
  broll: false,
  captionScript: 'auto',
};

export const STRENGTH_OPTIONS = [
  { value: 'light', label: 'Light' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'maximum', label: 'Maximum' },
] as const satisfies ReadonlyArray<{ value: StudioVoiceLevel; label: string }>;

export const SCRIPT_OPTIONS = [
  { value: 'auto', label: 'Auto' },
  { value: 'roman', label: 'Roman' },
  { value: 'native', label: 'Native' },
] as const satisfies ReadonlyArray<{ value: CaptionScript; label: string }>;

const LENGTH_SHORT: Record<LengthChoiceId, string> = { short: 'Under 30 s', medium: '30–45 s', long: '45–60 s' };

export const LENGTH_OPTIONS = [
  { value: 'auto', label: 'Auto', ariaLabel: 'Any length, Clipnera decides' },
  ...LENGTH_CHOICES.map((choice) => ({ value: choice.id, label: LENGTH_SHORT[choice.id], ariaLabel: choice.label })),
] as const satisfies ReadonlyArray<{ value: RunOptions['length']; label: string; ariaLabel: string }>;

/** The one-line summary on the closed Options disclosure. */
export function summarize(options: RunOptions, brollAllowed: boolean): string {
  const parts = [
    options.formats.join(', '),
    options.studioVoice ? `Studio voice, ${STRENGTH_OPTIONS.find((o) => o.value === options.strength)!.label}` : 'Studio voice off',
    options.length === 'auto' ? 'Any length' : LENGTH_SHORT[options.length],
    `Captions ${options.captionScript}`,
  ];
  if (options.storyClips) parts.push('Story clips');
  if (brollAllowed && options.broll) parts.push('B-roll');
  return parts.join(' · ');
}

/** The `POST /pipeline/start` body for these choices. */
export function toRunRequest(options: RunOptions, prompt: string, brollAllowed: boolean): ClipRunRequest {
  const length = LENGTH_CHOICES.find((choice) => choice.id === options.length);
  const voice = options.studioVoice;
  const trimmed = prompt.trim();
  return {
    audio_config: {
      ai_denoise: voice,
      noise_suppression_strength: STUDIO_VOICE_STRENGTH[options.strength],
      de_reverb: voice && options.removeEcho,
      vocal_clarity_eq: voice && options.voiceClarity,
      hum_filter: voice && options.humFilter,
    },
    output_aspect_ratios: options.formats,
    clip_settings: {
      caption_script: options.captionScript,
      broll: brollAllowed && options.broll,
      story_clips: options.storyClips,
      ...(length ? { min_clip_duration: length.min, max_clip_duration: length.max } : {}),
      ...(trimmed ? { prompt: trimmed } : {}),
    },
  };
}
