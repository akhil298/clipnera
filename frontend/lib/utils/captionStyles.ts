import { CaptionPreset, CaptionConfig, WordTimestamp, TranscriptSegment } from '@/lib/types';

export interface CaptionStyle {
  id: CaptionPreset;
  name: string;
  description: string;
  badge: string;
  config: CaptionConfig;
}

export const captionStyles: Record<CaptionPreset, CaptionStyle> = {
  hormozi: {
    id: 'hormozi',
    name: 'Hormozi Viral',
    description: 'Bold uppercase, yellow/green highlights with dark backdrop',
    badge: 'Popular',
    config: {
      preset: 'hormozi',
      fontSize: 22,
      fontFamily: 'Syne',
      textColor: '#FFFFFF',
      highlightColor: '#FACC15',
      secondaryHighlightColor: '#4ADE80',
      hasBgBox: false,
      bgBoxColor: 'rgba(0,0,0,0.85)',
      uppercase: true,
      animation: 'bounce',
      positionY: 72,
      emojisEnabled: true,
      maxWordsPerLine: 3,
      shadowIntensity: 0.8,
    },
  },
  mrbeast: {
    id: 'mrbeast',
    name: 'MrBeast Pop',
    description: 'High energy electric blue + bright red punch text',
    badge: 'High CTR',
    config: {
      preset: 'mrbeast',
      fontSize: 24,
      fontFamily: 'Plus Jakarta Sans',
      textColor: '#FFFFFF',
      highlightColor: '#38BDF8',
      secondaryHighlightColor: '#F43F5E',
      hasBgBox: true,
      bgBoxColor: 'rgba(0,0,0,0.85)',
      uppercase: true,
      animation: 'pop',
      positionY: 70,
      emojisEnabled: true,
      maxWordsPerLine: 2,
      shadowIntensity: 0.9,
    },
  },
  karaoke_yellow: {
    id: 'karaoke_yellow',
    name: 'Karaoke Beat',
    description: 'Word-by-word active bouncing fill sync',
    badge: 'Top Watchtime',
    config: {
      preset: 'karaoke_yellow',
      fontSize: 26,
      fontFamily: 'Syne',
      textColor: '#94A3B8',
      highlightColor: '#FACC15',
      secondaryHighlightColor: '#FACC15',
      hasBgBox: false,
      bgBoxColor: 'rgba(0,0,0,0.85)',
      uppercase: false,
      animation: 'karaoke',
      positionY: 75,
      emojisEnabled: false,
      maxWordsPerLine: 4,
      shadowIntensity: 0.7,
    },
  },
  cyberpunk: {
    id: 'cyberpunk',
    name: 'Cyber Neon',
    description: 'Neon cyan with purple ambient glow',
    badge: 'Tech / Gaming',
    config: {
      preset: 'cyberpunk',
      fontSize: 22,
      fontFamily: 'JetBrains Mono',
      textColor: '#E0F2FE',
      highlightColor: '#38BDF8',
      secondaryHighlightColor: '#A855F7',
      hasBgBox: false,
      bgBoxColor: 'rgba(0,0,0,0.85)',
      uppercase: false,
      animation: 'glow',
      positionY: 70,
      emojisEnabled: true,
      maxWordsPerLine: 3,
      shadowIntensity: 1.0,
    },
  },
  minimal: {
    id: 'minimal',
    name: 'Clean Minimal',
    description: 'Understated elegant typography for luxury & podcasts',
    badge: 'Aesthetic',
    config: {
      preset: 'minimal',
      fontSize: 20,
      fontFamily: 'Plus Jakarta Sans',
      textColor: '#FFFFFF',
      highlightColor: '#E2E8F0',
      secondaryHighlightColor: '#E2E8F0',
      hasBgBox: false,
      bgBoxColor: 'transparent',
      uppercase: false,
      animation: 'wave',
      positionY: 72,
      emojisEnabled: false,
      maxWordsPerLine: 4,
      shadowIntensity: 0.5,
    },
  },
  neon: {
    id: 'neon',
    name: 'Neon Glow',
    description: 'Vibrant pink and green neon effect',
    badge: 'Trending',
    config: {
      preset: 'neon',
      fontSize: 24,
      fontFamily: 'Syne',
      textColor: '#FFFFFF',
      highlightColor: '#F0ABFC',
      secondaryHighlightColor: '#4ADE80',
      hasBgBox: false,
      bgBoxColor: 'rgba(0,0,0,0.6)',
      uppercase: true,
      animation: 'glow',
      positionY: 70,
      emojisEnabled: true,
      maxWordsPerLine: 2,
      shadowIntensity: 1.0,
    },
  },
  sunset: {
    id: 'sunset',
    name: 'Sunset Warm',
    description: 'Warm orange and red gradient highlights',
    badge: 'Lifestyle',
    config: {
      preset: 'sunset',
      fontSize: 22,
      fontFamily: 'Syne',
      textColor: '#FFFFFF',
      highlightColor: '#FB923C',
      secondaryHighlightColor: '#F87171',
      hasBgBox: false,
      bgBoxColor: 'rgba(0,0,0,0.7)',
      uppercase: false,
      animation: 'bounce',
      positionY: 72,
      emojisEnabled: true,
      maxWordsPerLine: 3,
      shadowIntensity: 0.8,
    },
  },
};

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
