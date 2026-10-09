'use client';

import type { CSSProperties } from 'react';

import { cx } from '@/lib/design/styles';
import type { CaptionConfig } from '@/lib/types';
import { captionRowSplit, captionTextStyle, captionWordColor } from '@/lib/utils/captionStyles';

/** The spoken word's pose per animation, read by the global `caption-word-cycle` keyframes. */
const MOTION: Record<CaptionConfig['animation'], { pop?: number; lift?: string; rotate?: string; skew?: string }> = {
  pop: { pop: 1.22 },
  wave: { pop: 1.06, lift: '-0.16em' },
  karaoke: {},
  glow: { pop: 1.08 },
  fade: {},
  none: {},
  land: { lift: '0.06em' },
  bounce: { pop: 1.06, lift: '-0.14em' },
  grow: {},
  breathe: {},
  blur: {},
  shake: { rotate: '-4deg' },
  glitch: { skew: '-12deg' },
};

/** Motions whose spoken word grows by the template's own scale. */
const SCALED = new Set<CaptionConfig['animation']>(['pop', 'grow', 'breathe']);

const SAMPLE_WORDS = ['THIS', 'CHANGES', 'EVERY', 'THING'];

export interface CaptionStyleSampleProps {
  /** The style's config, with any brand colours already applied. */
  config: CaptionConfig;
  words?: ReadonlyArray<string>;
  /** Rendered size in px. The template's own size is on a 1080-wide frame, so callers scale it down. */
  fontSize: number;
  className?: string;
  /** Placement inside a frame (`top`). */
  style?: CSSProperties;
}

/**
 * A live, looping sample of one caption style: the face, colours, outline,
 * rows, word box and motion the burned captions use (mirrors ass_generator.py
 * through lib/utils/captionStyles). The highlight travels in CSS with a
 * staggered delay, so a grid of 21 runs without a timer, and it holds still
 * under reduced motion. Decorative: the card or frame around it names the style.
 */
export function CaptionStyleSample({ config, words = SAMPLE_WORDS, fontSize, className, style }: CaptionStyleSampleProps) {
  const motion = MOTION[config.animation] ?? {};
  const pop = SCALED.has(config.animation) ? config.activeScale : motion.pop ?? 1;
  const split = captionRowSplit([...words], config.rows);
  const rows = [words.slice(0, split), words.slice(split)].filter((row) => row.length > 0);

  return (
    <div aria-hidden style={style} className={cx('flex flex-col items-center justify-center text-center leading-none', className)}>
      <div
        className="flex flex-col items-center"
        style={{
          ...captionTextStyle(config),
          fontSize: `${fontSize}px`,
          ...(config.hasBgBox ? { backgroundColor: config.bgBoxColor, padding: '0.2em 0.45em', borderRadius: '0.25em' } : {}),
        }}
      >
        {rows.map((row, r) => {
          const offset = r === 0 ? 0 : split;
          const second = offset > 0 || (split === 0 && config.rows > 1);
          return (
            <p key={r} className="flex flex-wrap items-center justify-center" style={second ? { fontSize: `${config.secondLineScale}em` } : undefined}>
              {row.map((word, i) => {
                const index = offset + i;
                const secondRow = index >= split && config.rows > 1;
                return (
                  <span
                    key={`${word}-${index}`}
                    className="caption-preview-word"
                    style={
                      {
                        '--cap-text': captionWordColor(config, 'upcoming', secondRow, false),
                        '--cap-hl': captionWordColor(config, 'active', secondRow, false),
                        '--cap-hl-bg': config.wordBoxColor ?? 'transparent',
                        '--cap-pop': String(pop),
                        '--cap-lift': motion.lift ?? '0px',
                        '--cap-rotate': motion.rotate ?? '0deg',
                        '--cap-skew': motion.skew ?? '0deg',
                        '--cap-idle-opacity': config.hideUpcoming ? '0.3' : '1',
                        animationDelay: `${index * 0.7}s`,
                      } as CSSProperties
                    }
                  >
                    {word}
                  </span>
                );
              })}
            </p>
          );
        })}
      </div>
    </div>
  );
}
