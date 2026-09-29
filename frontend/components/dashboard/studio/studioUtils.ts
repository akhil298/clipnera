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
import { pillTextColor } from '@/lib/utils/captionStyles';
import { getEmojiCollection } from '@/lib/data/emojiCollections';

/** Everything the Studio edits for one clip; undo and redo step through snapshots of it. */
export interface StudioDoc {
  aspectRatio: AspectRatio;
  captionConfig: CaptionConfig;
  hookTransition: HookTransitionConfig;
  watermarkEnabled: boolean;
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

/** CSS entrance for a caption line; mirrors _entrance() in ass_generator.py. */
export const captionEntrance = (animation: CaptionConfig['animation'], speed: number): string | undefined => {
  const pace = Math.max(0.25, speed || 1);
  if (animation === 'pop' || animation === 'wave') return `caption-rise ${Math.round(170 / pace)}ms ease-out`;
  if (animation === 'fade' || animation === 'glow') return `caption-fade ${Math.round(200 / pace)}ms ease-out`;
  return undefined;
};

/**
 * One caption word's look; mirrors _active_word_tags() in ass_generator.py. On
 * a plate the spoken word sits in a pill of the secondary highlight colour,
 * and the emphasis colour is not used for text.
 */
export const activeWordStyle = (config: CaptionConfig, isActive: boolean, highlighted: boolean): React.CSSProperties => {
  const onPlate = config.hasBgBox;
  if (!isActive) {
    return {
      color: highlighted && !onPlate ? config.secondaryHighlightColor : config.textColor,
      transform: 'scale(1)',
    };
  }
  const motion =
    config.animation === 'pop' ? 'scale(1.09)' : config.animation === 'wave' ? 'translateY(-8%) scale(1.06)' : 'scale(1)';
  if (onPlate) {
    return {
      color: pillTextColor(config),
      backgroundColor: config.secondaryHighlightColor,
      borderRadius: '0.3em',
      padding: '0 0.2em',
      transform: motion,
    };
  }
  return {
    color: config.highlightColor,
    transform: motion,
    ...(config.animation === 'glow' ? { textShadow: `0 0 12px ${config.highlightColor}` } : {}),
  };
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

/**
 * Captions flow as short phrases, mirroring the ASS burner's grouping, so the
 * preview shows the same line breaks the exported video will have.
 */
export const groupCaptionWords = (words: WordTimestamp[], maxWordsPerLine: number): WordTimestamp[][] => {
  const maxWords = Math.max(1, maxWordsPerLine);
  const GAP_BREAK = 0.6; // a pause this long starts a new line
  const groups: WordTimestamp[][] = [];
  let current: WordTimestamp[] = [];
  for (const word of words) {
    const previous = current[current.length - 1];
    if (current.length >= maxWords || (previous && word.start - previous.end > GAP_BREAK)) {
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
