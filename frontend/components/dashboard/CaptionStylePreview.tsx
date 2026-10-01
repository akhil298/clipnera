"use client";
import React from 'react';
import { CaptionConfig } from '@/lib/types';
import { captionRowSplit, captionTextStyle, captionWordColor } from '@/lib/utils/captionStyles';

interface CaptionStylePreviewProps {
  config: CaptionConfig;
  /** Words shown in the preview. Four keeps every card the same rhythm. */
  words?: string[];
  className?: string;
  /** Font size in px; defaults to the template's size scaled into a card-sized band. */
  fontSize?: number;
  /** Drop the card backdrop, for previews laid over footage. */
  overlay?: boolean;
}

const SAMPLE_WORDS = ['THIS', 'CHANGES', 'EVERY', 'THING'];

interface Motion {
  pop?: number;
  lift?: string;
  rotate?: string;
  skew?: string;
}

/** The spoken word's pose per animation, as the custom properties the keyframes read. */
const MOTION: Record<CaptionConfig['animation'], Motion> = {
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

/**
 * A live, looping sample of one caption template.
 *
 * Reads as the thing it describes rather than a sentence about it: the same
 * face, colours, outline, rows, highlight treatment and motion the burned
 * captions use. The highlight travels in pure CSS with a staggered
 * `animation-delay`, so a list of twenty previews runs without a JS timer.
 */
export const CaptionStylePreview: React.FC<CaptionStylePreviewProps> = ({
  config,
  words = SAMPLE_WORDS,
  className = '',
  fontSize,
  overlay = false,
}) => {
  const motion = MOTION[config.animation] ?? {};
  const pop = SCALED.has(config.animation) ? config.activeScale : motion.pop ?? 1;

  // The card is a fixed size, so the template's real px font size would overflow
  // the wide presets and look lost on the small ones. Scaled into a legible band
  // that still preserves the relative difference between templates.
  const previewFontSize = fontSize ?? Math.round(Math.min(22, Math.max(11, config.fontSize * 0.21)));
  const split = captionRowSplit(words, config.rows);
  const rows = [words.slice(0, split), words.slice(split)].filter((row) => row.length > 0);

  const renderWord = (word: string, index: number) => {
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
          } as React.CSSProperties
        }
      >
        {word}
      </span>
    );
  };

  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden ${overlay ? '' : 'rounded-lg bg-black/60 px-2 py-2.5'} ${className}`}
      aria-hidden="true"
    >
      {/* A faint checker keeps light-on-light templates legible against the card. */}
      {!overlay && <div
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            'linear-gradient(45deg,#fff 25%,transparent 25%,transparent 75%,#fff 75%),linear-gradient(45deg,#fff 25%,transparent 25%,transparent 75%,#fff 75%)',
          backgroundSize: '10px 10px',
          backgroundPosition: '0 0, 5px 5px',
        }}
      />}

      <div
        className="relative flex flex-col items-center justify-center text-center leading-[1.05]"
        style={{
          ...captionTextStyle(config),
          fontSize: `${previewFontSize}px`,
          ...(config.hasBgBox
            ? { backgroundColor: config.bgBoxColor, padding: '0.2em 0.45em', borderRadius: '0.25em' }
            : {}),
        }}
      >
        {rows.map((row, r) => {
          const offset = r === 0 ? 0 : split;
          const second = offset > 0 || (split === 0 && config.rows > 1);
          return (
            <p
              key={r}
              className="flex flex-wrap items-center justify-center gap-x-[0.2em]"
              style={second ? { fontSize: `${config.secondLineScale}em` } : undefined}
            >
              {row.map((word, i) => renderWord(word, offset + i))}
            </p>
          );
        })}
      </div>
    </div>
  );
};
