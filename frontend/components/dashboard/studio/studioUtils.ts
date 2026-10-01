import type React from 'react';
import {
  AspectRatio,
  AudioEnhancementConfig,
  AutoZoomConfig,
  BRollOverlay,
  CaptionConfig,
  HookTransitionConfig,
  SoundEffect,
  TranscriptSegment,
  WordTimestamp,
} from '@/lib/types';
import { captionWordColor, type CaptionWordState } from '@/lib/utils/captionStyles';
import { getEmojiCollection } from '@/lib/data/emojiCollections';

/** Everything the Studio edits for one clip; undo and redo step through snapshots of it. */
export interface StudioDoc {
  aspectRatio: AspectRatio;
  captionConfig: CaptionConfig;
  hookTransition: HookTransitionConfig;
  watermarkEnabled: boolean;
  /** Burn captions into the export. */
  captionsEnabled: boolean;
  /** Overlay the clip title; only exported with captions on. */
  titleEnabled: boolean;
  /** Cut words by source start time; the words stay in the transcript, struck through. */
  removedWords: number[];
  transcriptSegments: TranscriptSegment[];
  bRollOverlays: BRollOverlay[];
  soundEffects: SoundEffect[];
  autoZoom: AutoZoomConfig;
  audioEnhancement: AudioEnhancementConfig;
}

export type StudioTool = 'captions' | 'hook' | 'broll' | 'sfx' | 'audio' | 'format';
export type Platform = 'tiktok' | 'reels' | 'shorts';
export type PreviewMode = 'none' | Platform;

export interface TimeRange {
  start: number;
  end: number;
}

/**
 * Where each app draws its own UI over a vertical video, as a share of the
 * frame (approximate; the apps change them over time). Captions inside these
 * bands end up under the caption text, handle or buttons.
 */
export const SAFE_ZONES: Record<Platform, { name: string; top: number; bottom: number; right: number }> = {
  tiktok: { name: 'TikTok', top: 13, bottom: 26, right: 16 },
  reels: { name: 'Instagram Reels', top: 14, bottom: 34, right: 15 },
  shorts: { name: 'YouTube Shorts', top: 12, bottom: 28, right: 16 },
};

/** The zones to check against: the previewed platform, else Reels, the tightest. */
export const safeZoneFor = (preview: PreviewMode) => SAFE_ZONES[preview === 'none' ? 'reels' : preview];

/** Whether a caption centred at `positionY`% sits between a platform's top and bottom bands. */
export const captionsClear = (positionY: number, zone: { top: number; bottom: number }): boolean =>
  positionY >= zone.top && positionY <= 100 - zone.bottom;

/** Caption position limits; the burner accepts the same range. */
export const CAPTION_Y_MIN = 20;
export const CAPTION_Y_MAX = 90;

/** Exported frame size per aspect ratio; mirrors output_dimensions() in video_processor/geometry.py. */
export const EXPORT_SIZE: Record<AspectRatio, string> = {
  '9:16': '1080×1920',
  '4:5': '1080×1350',
  '1:1': '1080×1080',
  '16:9': '1920×1080',
};

export const DEFAULT_AUDIO_ENHANCEMENT: AudioEnhancementConfig = {
  aiDenoise: true,
  noiseSuppressionStrength: 90,
  deReverb: true,
  vocalClarityEq: true,
  humFilter: true,
};

/** Player clock, e.g. 75.4 -> "1:15". */
export const formatClock = (seconds: number): string => {
  const whole = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
};

/** Clock with tenths, e.g. 14.34 -> "0:14.3". */
export const formatPrecise = (seconds: number): string => {
  const safe = Math.max(0, seconds || 0);
  const minutes = Math.floor(safe / 60);
  return `${minutes}:${(safe - minutes * 60).toFixed(1).padStart(4, '0')}`;
};

/** What the export is doing, judged from the paced progress bar. */
export const exportStage = (progress: number): string =>
  progress < 30
    ? 'Preparing your clip...'
    : progress < 60
    ? 'Burning in captions and title...'
    : progress < 85
    ? 'Encoding the video...'
    : 'Almost done, uploading your file...';

/** CSS entrance for a caption line; mirrors _entrance() and _word_entrance() in ass_generator.py. */
export const captionEntrance = (animation: CaptionConfig['animation'], speed: number): string | undefined => {
  const pace = Math.max(0.25, speed || 1);
  const ms = (base: number) => `${Math.round(base / pace)}ms`;
  switch (animation) {
    case 'pop':
    case 'wave':
      return `caption-rise ${ms(170)} ease-out`;
    case 'land':
      return `caption-land ${ms(260)} ease-out`;
    case 'bounce':
      return `caption-bounce ${ms(260)} ease-out`;
    case 'grow':
      return `caption-grow ${ms(140)} ease-out`;
    case 'blur':
      return `caption-blur ${ms(220)} ease-out`;
    case 'fade':
    case 'glow':
      return `caption-fade ${ms(200)} ease-out`;
    case 'shake':
    case 'breathe':
    case 'glitch':
      return `caption-fade ${ms(100)} ease-out`;
    default:
      return undefined;
  }
};

/** The spoken word's keyframes per animation, with their duration at 1x. */
const WORD_MOTION: Partial<Record<CaptionConfig['animation'], [string, number]>> = {
  pop: ['word-grow', 70],
  grow: ['word-grow', 150],
  breathe: ['word-breathe', 540],
  bounce: ['word-bounce', 210],
  shake: ['word-shake', 175],
  glitch: ['word-glitch', 180],
  blur: ['word-blur', 180],
};

/**
 * One caption word's look; mirrors _render_group() in ass_generator.py.
 * ``scale`` is the word's resting size (the second row of a stacked style
 * can be larger), around which the spoken word moves.
 */
export const captionWordStyle = (
  config: CaptionConfig,
  state: CaptionWordState,
  scale: number,
  emphasised: boolean,
  secondRow: boolean,
): React.CSSProperties => {
  const color = captionWordColor(config, state, secondRow, emphasised);
  const rest: React.CSSProperties = { color, transform: `scale(${scale})` };
  if (state === 'upcoming' && config.hideUpcoming) return { ...rest, opacity: 0 };
  if (state !== 'active' || config.animation === 'none') return rest;

  const [keyframes, duration] = WORD_MOTION[config.animation] ?? [];
  const grow = scale * (config.animation === 'pop' || config.animation === 'grow' || config.animation === 'breathe' ? config.activeScale : 1);
  const pace = Math.max(0.25, config.animationSpeed || 1);
  return {
    ...rest,
    transform: `scale(${grow})`,
    '--word-scale': String(scale),
    '--word-grow': String(grow),
    '--word-from-opacity': config.hideUpcoming ? '0' : '1',
    ...(keyframes ? { animation: `${keyframes} ${Math.round(duration! / pace)}ms ease-out both` } : {}),
    ...(config.wordBoxColor ? { backgroundColor: config.wordBoxColor, borderRadius: '0.12em' } : {}),
    ...(config.animation === 'glow' ? { textShadow: `0 0 12px ${color}` } : {}),
  } as React.CSSProperties;
};

/** Puts the chosen emoji set into the title the way the burner does. */
export const applyEmojiCollection = (text: string, collectionId?: string): string => {
  if (!collectionId) return text;
  const collection = getEmojiCollection(collectionId);
  if (!collection.emojis || collection.emojis.length === 0) return text;
  const spaces: number[] = [];
  for (let i = 0; i < text.length; i++) {
    if (text[i] === ' ') spaces.push(i);
  }
  if (spaces.length < 2) return `${text} ${collection.emojis.join(' ')}`;
  const firstBreak = spaces[0] + 1;
  const lastBreak = spaces[spaces.length - 1];
  const prefixEmojis = collection.emojis.slice(0, 2).join(' ');
  const middleText = text.slice(firstBreak, lastBreak).trim();
  const suffixText = text.slice(lastBreak).trim();
  return `${text.slice(0, firstBreak)}${prefixEmojis} ${middleText} ${suffixText}`;
};

/** Whether a word was cut. Words without a source time cannot be cut: the export could not find them. */
export const isWordCut = (word: WordTimestamp, removed: ReadonlySet<number>): boolean =>
  word.sourceStart !== undefined && removed.has(word.sourceStart);

// Mirrors PHRASE_PAUSE_SECONDS, CLAUSE_ENDINGS and DISPLAY_TRIM in the ASS burner.
const PHRASE_PAUSE_SECONDS = 0.35;
const CLAUSE_ENDING = /[.,?!;:…]$/;
const DISPLAY_TRIM = /^[.,?!;:…"“”—–]+|[.,?!;:…"“”—–]+$/g;

/** A caption word as burned: its surrounding punctuation trimmed. */
export const displayWord = (text: string): string => text.trim().replace(DISPLAY_TRIM, '');

/**
 * Captions flow as short phrases, mirroring the ASS burner's grouping, so the
 * preview shows the same line breaks the exported video will have.
 */
export const groupCaptionWords = (words: WordTimestamp[], maxWordsPerLine: number): WordTimestamp[][] => {
  const maxWords = Math.max(1, maxWordsPerLine);
  const groups: WordTimestamp[][] = [];
  let current: WordTimestamp[] = [];
  for (const word of words) {
    const previous = current[current.length - 1];
    const phraseEnds =
      previous && (CLAUSE_ENDING.test(previous.text.trim()) || word.start - previous.end >= PHRASE_PAUSE_SECONDS);
    if (current.length >= maxWords || phraseEnds) {
      groups.push(current);
      current = [];
    }
    current.push(word);
  }
  if (current.length) groups.push(current);
  return groups;
};

/** Runs of consecutive cut words, as clip-time ranges the preview skips over. */
export const cutRanges = (words: WordTimestamp[], removed: ReadonlySet<number>): TimeRange[] => {
  const ranges: TimeRange[] = [];
  let open: TimeRange | null = null;
  for (const word of words) {
    if (isWordCut(word, removed)) {
      if (open) open.end = Math.max(open.end, word.end);
      else open = { start: word.start, end: word.end };
    } else if (open) {
      ranges.push(open);
      open = null;
    }
  }
  if (open) ranges.push(open);
  return ranges;
};

/** True while the user is typing, so single-key shortcuts leave the keystroke alone. */
export const isTypingTarget = (target: EventTarget | null): boolean =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
