import type { CSSProperties } from 'react';

import type { CaptionConfig } from '@/lib/types';
import { captionRowSplit, captionTextStyle, captionWordColor } from '@/lib/utils/captionStyles';

/** The spoken word's pose per animation, read by the global `.caption-preview-word` keyframes. */
const MOTION: Partial<Record<CaptionConfig['animation'], { pop?: number; lift?: string; rotate?: string; skew?: string }>> = {
  pop: { pop: 1.22 },
  wave: { pop: 1.06, lift: '-0.16em' },
  glow: { pop: 1.08 },
  land: { lift: '0.06em' },
  bounce: { pop: 1.06, lift: '-0.14em' },
  shake: { rotate: '-4deg' },
  glitch: { skew: '-12deg' },
};
const SCALED = new Set<CaptionConfig['animation']>(['pop', 'grow', 'breathe']);

interface CaptionSampleProps {
  config: CaptionConfig;
  words: string[];
  /** Font size in px for this placement. */
  fontSize: number;
}

/**
 * One caption style drawn the way the export burns it (face, colours, outline,
 * rows, highlight, motion). The highlight travels in CSS; under reduced motion
 * it holds still (globals.css). Decorative: the surrounding control names the style.
 */
export function CaptionSample({ config, words, fontSize }: CaptionSampleProps) {
  const motion = MOTION[config.animation] ?? {};
  const pop = SCALED.has(config.animation) ? config.activeScale : (motion.pop ?? 1);
  const split = captionRowSplit(words, config.rows);
  const rows = [words.slice(0, split), words.slice(split)].filter((row) => row.length > 0);

  return (
    <div
      aria-hidden
      className="flex flex-col items-center justify-center text-center leading-none"
      style={{
        ...captionTextStyle(config),
        fontSize,
        ...(config.hasBgBox ? { backgroundColor: config.bgBoxColor, padding: '0.2em 0.45em', borderRadius: '0.25em' } : {}),
      }}
    >
      {rows.map((row, r) => {
        const offset = r === 0 ? 0 : split;
        return (
          <p key={r} className="flex flex-wrap justify-center gap-x-1" style={offset > 0 ? { fontSize: `${config.secondLineScale}em` } : undefined}>
            {row.map((word, i) => {
              const index = offset + i;
              const secondRow = index >= split && config.rows > 1;
              const style = {
                '--cap-text': captionWordColor(config, 'upcoming', secondRow, false),
                '--cap-hl': captionWordColor(config, 'active', secondRow, false),
                '--cap-hl-bg': config.wordBoxColor ?? 'transparent',
                '--cap-pop': String(pop),
                '--cap-lift': motion.lift ?? '0px',
                '--cap-rotate': motion.rotate ?? '0deg',
                '--cap-skew': motion.skew ?? '0deg',
                '--cap-idle-opacity': config.hideUpcoming ? '0.3' : '1',
                animationDelay: `${index * 0.7}s`,
              } as CSSProperties;
              return (
                <span key={`${word}-${index}`} className="caption-preview-word" style={style}>
                  {word}
                </span>
              );
            })}
          </p>
        );
      })}
    </div>
  );
}
