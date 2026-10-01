import type { CSSProperties } from 'react';
import { CaptionConfig, WordTimestamp, TranscriptSegment } from '@/lib/types';
import {
  CaptionPreset,
  CaptionStyle,
  DEFAULT_CAPTION_PRESET,
  LEGACY_CAPTION_PRESETS,
  captionStyles,
} from '@/lib/utils/captionStyles.generated';


export type { CaptionPreset, CaptionStyle };
export { captionStyles, DEFAULT_CAPTION_PRESET };

/** A current style id for any stored one: itself, its replacement, or the default. Mirrors resolve_style_id(). */
export const resolveCaptionPreset = (preset: string | undefined): CaptionPreset =>
  preset && preset in captionStyles
    ? (preset as CaptionPreset)
    : LEGACY_CAPTION_PRESETS[preset ?? ''] ?? DEFAULT_CAPTION_PRESET;

export const getCaptionStyle = (preset: CaptionPreset): CaptionStyle => {
  return captionStyles[resolveCaptionPreset(preset)];
};

/**
 * A saved caption config brought up to the current catalogue. A current style
 * keeps the user's edits over any fields added since it was saved; a retired
 * one takes its replacement's whole look, keeping only placement and
 * preferences, since its old colours and font belong to a style that is gone.
 */
export const normalizeCaptionConfig = (saved: Partial<CaptionConfig> | undefined): CaptionConfig => {
  const preset = resolveCaptionPreset(saved?.preset);
  const base = getCaptionConfig(preset);
  if (!saved) return base;
  if (saved.preset === preset) return { ...base, ...saved };
  const kept = (['positionY', 'emojisEnabled', 'emojiCollection', 'animationSpeed', 'titleFontSize', 'titlePositionY'] as const)
    .filter((key) => saved[key] !== undefined)
    .reduce((acc, key) => ({ ...acc, [key]: saved[key] }), {} as Partial<CaptionConfig>);
  return { ...base, ...kept };
};

export const getCaptionConfig = (preset: CaptionPreset): CaptionConfig => {
  return getCaptionStyle(preset).config;
};

export const getAllCaptionStyles = (): CaptionStyle[] => {
  return Object.values(captionStyles);
};

export const getCaptionPresetIds = (): CaptionPreset[] => {
  return Object.keys(captionStyles) as CaptionPreset[];
};

/**
 * Text colour for the spoken word on its pill; mirrors _active_colour() in
 * ass_generator.py. Falls back to black or white when both the highlight and
 * the text colour match the pill.
 */
export const pillTextColor = (config: CaptionConfig): string => {
  const pill = (config.wordBoxColor ?? '').toLowerCase();
  const readable = [config.highlightColor, config.textColor].find((colour) => colour.toLowerCase() !== pill);
  if (readable) return readable;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(pill.slice(i, i + 2), 16) || 0);
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? '#000000' : '#FFFFFF';
};

/**
 * Index of the first word on the second row; ``words.length`` for one row.
 * Mirrors _row_split() in ass_generator.py: a lone word takes the second row.
 */
export const captionRowSplit = (words: string[], rows: number): number => {
  if (rows < 2) return words.length;
  if (words.length < 2) return 0;
  const half = (words.reduce((sum, word) => sum + word.length, 0) + words.length - 1) / 2;
  let split = 0;
  let chars = -1;
  for (const word of words.slice(0, -1)) {
    chars += word.length + 1;
    if (split && chars > half) break;
    split += 1;
  }
  return split;
};

/**
 * Face, casing, outline, shadow and glow shared by every word of a caption
 * line; mirrors the Caption style in ass_generator.py.
 */
export const captionTextStyle = (config: CaptionConfig): CSSProperties => {
  // The burn's outline is stroke_width * 0.8 px against a font_size * 1.75 px
  // em. A CSS stroke is centred on the glyph edge, so it is drawn twice as wide
  // and painted under the fill to show the same outer width.
  const stroked = Boolean(config.strokeColor) && config.strokeWidth > 0 && !config.hasBgBox;
  const strokeEm = stroked ? (config.strokeWidth * 1.6) / (config.fontSize * 1.75) : 0;
  const shadows: string[] = [];
  if (config.shadowIntensity > 0 && !config.hasBgBox) shadows.push(`0 0.06em 0.12em rgba(0,0,0,${0.85 * config.shadowIntensity})`);
  if (config.glow) {
    const halo = config.strokeColor ?? config.highlightColor;
    shadows.push(`0 0 0.2em ${halo}`, `0 0 0.45em ${halo}`);
  }
  return {
    fontFamily: config.fontFamily,
    fontWeight: config.fontWeight,
    fontStyle: config.italic ? 'italic' : 'normal',
    textTransform: config.uppercase ? 'uppercase' : 'none',
    WebkitTextStroke: stroked ? `${strokeEm.toFixed(3)}em ${config.strokeColor}` : undefined,
    paintOrder: 'stroke fill',
    textShadow: shadows.length ? shadows.join(', ') : 'none',
  };
};

export type CaptionWordState = 'spoken' | 'active' | 'upcoming';

/** One caption word's colour; mirrors _active_colour() and _rest_colour() in ass_generator.py. */
export const captionWordColor = (
  config: CaptionConfig,
  state: CaptionWordState,
  secondRow: boolean,
  emphasised: boolean,
): string => {
  const onPill = config.hasBgBox && Boolean(config.wordBoxColor);
  if (state === 'active') {
    if (onPill) return pillTextColor(config);
    return secondRow && config.secondLineColor ? config.secondLineColor : config.highlightColor;
  }
  if (secondRow && config.secondLineColor) return config.secondLineColor;
  if (state === 'upcoming' && config.upcomingColor) return config.upcomingColor;
  if (emphasised && !onPill) return config.secondaryHighlightColor;
  return config.textColor;
};

export interface StyledWord extends WordTimestamp {
  style: CaptionConfig;
  color: string;
  isHighlighted: boolean;
}

export interface StyledCaptionSegment {
  id: string;
  speaker: string;
  speakerColor: string;
  start: number;
  end: number;
  text: string;
  words: StyledWord[];
  style: CaptionConfig;
}

export const applyStyleToTranscript = (
  segments: TranscriptSegment[],
  preset: CaptionPreset,
): StyledCaptionSegment[] => {
  const style = getCaptionConfig(preset);
  return segments.map((segment) => ({
    ...segment,
    style,
    words: segment.words.map((word) => ({
      ...word,
      style,
      color: word.highlighted ? style.highlightColor : style.textColor,
      isHighlighted: word.highlighted ?? false,
    })),
  }));
};

export const getWordsForTimeRange = (
  segments: StyledCaptionSegment[],
  currentTime: number,
  windowSeconds: number = 2,
): StyledWord[] => {
  const words: StyledWord[] = [];
  for (const segment of segments) {
    for (const word of segment.words) {
      if (word.start >= currentTime - windowSeconds && word.end <= currentTime + windowSeconds) {
        words.push(word);
      }
    }
  }
  return words.sort((a, b) => a.start - b.start);
};

export const getActiveWordsAtTime = (
  segments: StyledCaptionSegment[],
  currentTime: number,
): StyledWord[] => {
  const words: StyledWord[] = [];
  for (const segment of segments) {
    for (const word of segment.words) {
      if (currentTime >= word.start && currentTime <= word.end) {
        words.push({ ...word, isHighlighted: true, color: word.style.highlightColor });
      }
    }
  }
  return words;
};
