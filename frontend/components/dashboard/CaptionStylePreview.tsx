"use client";
import React from 'react';
import { CaptionConfig } from '@/lib/types';

interface CaptionStylePreviewProps {
  config: CaptionConfig;
  /** Words shown in the preview. Four keeps every card the same rhythm. */
  words?: string[];
  className?: string;
}

const SAMPLE_WORDS = ['THIS', 'CHANGES', 'EVERY', 'THING'];

/** Per-animation motion, expressed as the custom properties the keyframes read. */
const MOTION: Record<CaptionConfig['animation'], { pop: string; lift: string; idleOpacity: string }> = {
  pop: { pop: '1.22', lift: '0px', idleOpacity: '1' },
  wave: { pop: '1.06', lift: '-0.16em', idleOpacity: '1' },
  karaoke: { pop: '1', lift: '0px', idleOpacity: '1' },
  glow: { pop: '1.08', lift: '0px', idleOpacity: '1' },
  fade: { pop: '1', lift: '0px', idleOpacity: '0.45' },
  none: { pop: '1', lift: '0px', idleOpacity: '1' },
};

/**
 * A live, looping sample of one caption template.
 *
 * Reads as the thing it describes rather than a sentence about it: the same
 * colours, weight, casing, highlight treatment and motion the burned captions
 * use. The highlight travels in pure CSS with a staggered `animation-delay`, so
 * a list of twenty previews runs without a single JS timer.
 */
export const CaptionStylePreview: React.FC<CaptionStylePreviewProps> = ({
  config,
  words = SAMPLE_WORDS,
  className = '',
}) => {
  const motion = MOTION[config.animation] ?? MOTION.none;
  const text = config.uppercase ? (w: string) => w.toUpperCase() : (w: string) => w;

  // The card is a fixed size, so the template's real px font size would overflow
  // the wide presets and look lost on the small ones. Scaled into a legible band
  // that still preserves the relative difference between templates.
  const previewFontSize = Math.round(Math.min(22, Math.max(11, config.fontSize * 0.42)));

  const shadow = config.shadowIntensity > 0
    ? `0 ${Math.round(config.shadowIntensity * 2)}px ${Math.round(config.shadowIntensity * 5)}px rgba(0,0,0,0.85)`
    : 'none';
  const glow = config.animation === 'glow'
    ? `, 0 0 10px ${config.highlightColor}, 0 0 20px ${config.highlightColor}`
    : '';

  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden rounded-lg bg-black/60 px-2 py-2.5 ${className}`}
      aria-hidden="true"
    >
      {/* A faint checker keeps light-on-light templates legible against the card. */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            'linear-gradient(45deg,#fff 25%,transparent 25%,transparent 75%,#fff 75%),linear-gradient(45deg,#fff 25%,transparent 25%,transparent 75%,#fff 75%)',
          backgroundSize: '10px 10px',
          backgroundPosition: '0 0, 5px 5px',
        }}
      />

      <p
        className="relative flex flex-wrap items-center justify-center gap-x-1 gap-y-0.5 text-center leading-tight"
        style={{
          fontFamily: config.fontFamily,
          fontSize: `${previewFontSize}px`,
          fontWeight: 800,
          textShadow: `${shadow}${glow}`,
          ...(config.hasBgBox
            ? { backgroundColor: config.bgBoxColor, padding: '0.2em 0.45em', borderRadius: '0.35em' }
            : {}),
        }}
      >
        {words.map((word, index) => (
          <span
            key={`${word}-${index}`}
            className="caption-preview-word"
            style={
              {
                '--cap-text': config.textColor,
                '--cap-hl': config.highlightColor,
                // Hormozi-style templates paint a pill behind the active word;
                // the rest highlight by colour alone.
                '--cap-hl-bg': config.hasBgBox ? config.secondaryHighlightColor : 'transparent',
                '--cap-pop': motion.pop,
                '--cap-lift': motion.lift,
                '--cap-idle-opacity': motion.idleOpacity,
                color: config.textColor,
                animationDelay: `${index * 0.7}s`,
              } as React.CSSProperties
            }
          >
            {text(word)}
          </span>
        ))}
      </p>
    </div>
  );
};
