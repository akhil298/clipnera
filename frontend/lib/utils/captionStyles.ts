import { CaptionConfig, WordTimestamp, TranscriptSegment } from '@/lib/types';
import { CaptionPreset, CaptionStyle, captionStyles } from '@/lib/utils/captionStyles.generated';


export type { CaptionPreset, CaptionStyle };
export { captionStyles };

export const getCaptionStyle = (preset: CaptionPreset): CaptionStyle => {
  return captionStyles[preset] ?? captionStyles.hormozi;
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
 * Text colour for the spoken word on its pill; mirrors _active_word_tags() in
 * ass_generator.py. Falls back to black or white when both the highlight and
 * the text colour match the pill (Minimal is white on white).
 */
export const pillTextColor = (config: CaptionConfig): string => {
  const pill = config.secondaryHighlightColor.toLowerCase();
  const readable = [config.highlightColor, config.textColor].find((colour) => colour.toLowerCase() !== pill);
  if (readable) return readable;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(pill.slice(i, i + 2), 16) || 0);
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? '#000000' : '#FFFFFF';
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
