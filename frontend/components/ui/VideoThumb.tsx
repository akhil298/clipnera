'use client';

import { Film } from 'lucide-react';
import { type PointerEvent, type ReactNode, useState } from 'react';

import { cx } from '@/lib/design/styles';
import { formatTimecode, spokenDuration } from '@/lib/design/timecode';
import { useHoverIntent } from '@/lib/design/useHoverIntent';

export type ThumbAspect = '9:16' | '16:9' | '1:1';

/** Aspect classes shared by every media tile. 9:16 waits on an `aspect-cn-portrait` token. */
export const ASPECT_CLASS: Record<ThumbAspect, string> = {
  '9:16': 'aspect-[9/16]',
  '16:9': 'aspect-video',
  '1:1': 'aspect-square',
};

const CHIP = 'rounded-cn-xs bg-cn-bg/80 px-1.5 text-cn-caption text-cn-fg';

/** A clip's score on a poster: amber from 85, emerald from 70, neutral below; the number is always shown. */
export function ScoreBadge({ score, className }: { score: number; className?: string }) {
  const tone = score >= 85 ? 'text-cn-accent-text' : score >= 70 ? 'text-cn-success-text' : 'text-cn-fg-secondary';
  return (
    <span className={cx(CHIP, 'inline-flex items-center gap-1 font-cn-mono font-semibold tabular-nums', tone, className)}>
      <span aria-hidden>{Math.round(score)}</span>
      <span className="sr-only">Score {Math.round(score)} out of 100</span>
    </span>
  );
}

export interface VideoThumbProps {
  /** Poster image URL. Missing or broken shows the neutral film tile. */
  poster?: string;
  aspect?: ThumbAspect;
  /** Length in seconds; shown bottom right. */
  duration?: number;
  score?: number;
  /** Muted proxy to play on hover or focus after 150 ms. Never under reduced motion. */
  previewSrc?: string;
  /** Drive the preview from outside (a card that owns hover); otherwise the thumb tracks its own hover. */
  previewing?: boolean;
  /**
   * Hover-scrub hook point: called with 0–1 as the pointer moves across, so a
   * caller can swap in a sprite frame or seek the preview. A thin playhead marks the spot.
   */
  onScrub?: (fraction: number) => void;
  /** Slots on the poster. Keep them small (badges, a checkbox, a menu). */
  topLeft?: ReactNode;
  topRight?: ReactNode;
  bottomLeft?: ReactNode;
  /** Dimmed with 50% opacity: taken down, licence expired, processing. */
  dimmed?: boolean;
  /** Selected tiles get the 2px accent edge. */
  selected?: boolean;
  rounded?: 'md' | 'lg';
  className?: string;
}

/**
 * A video poster with its duration, optional score and hover preview (02 §5.4).
 * Decorative to screen readers: the card's link or button names the video.
 */
export function VideoThumb({
  poster,
  aspect = '9:16',
  duration,
  score,
  previewSrc,
  previewing,
  onScrub,
  topLeft,
  topRight,
  bottomLeft,
  dimmed = false,
  selected = false,
  rounded = 'md',
  className,
}: VideoThumbProps) {
  const [broken, setBroken] = useState(false);
  const [scrub, setScrub] = useState<number | null>(null);
  const { active, handlers } = useHoverIntent(undefined, Boolean(previewSrc) && previewing === undefined);
  const playing = Boolean(previewSrc) && (previewing ?? active);

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!onScrub) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const fraction = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    setScrub(fraction);
    onScrub(fraction);
  };

  return (
    <div
      {...handlers}
      onPointerMove={onPointerMove}
      onPointerLeave={() => {
        handlers.onPointerLeave();
        setScrub(null);
      }}
      className={cx(
        'relative isolate overflow-hidden border bg-cn-surface-active',
        rounded === 'lg' ? 'rounded-cn-lg' : 'rounded-cn-md',
        selected ? 'border-cn-accent-border ring-1 ring-cn-accent-border' : 'border-cn-border',
        ASPECT_CLASS[aspect],
        className,
      )}
    >
      <div className={cx('absolute inset-0', dimmed && 'opacity-50')}>
        {poster && !broken ? (
          <img src={poster} alt="" loading="lazy" decoding="async" onError={() => setBroken(true)} className="size-full object-cover" />
        ) : (
          <Film aria-hidden className="absolute left-1/2 top-1/2 size-6 -translate-x-1/2 -translate-y-1/2 text-cn-fg-disabled" />
        )}
        {playing && (
          <video
            aria-hidden
            src={previewSrc}
            muted
            playsInline
            autoPlay
            loop
            preload="metadata"
            className="absolute inset-0 size-full object-cover motion-safe:animate-in motion-safe:fade-in motion-safe:duration-cn-fast"
          />
        )}
      </div>
      {scrub !== null && <span aria-hidden className="absolute inset-y-0 w-0.5 bg-cn-accent" style={{ left: `${scrub * 100}%` }} />}
      {topLeft && <div className="absolute left-1.5 top-1.5 z-cn-raised flex items-center gap-1">{topLeft}</div>}
      {(topRight || score !== undefined) && (
        <div className="absolute right-1.5 top-1.5 z-cn-raised flex items-center gap-1">
          {score !== undefined && <ScoreBadge score={score} />}
          {topRight}
        </div>
      )}
      {bottomLeft && <div className="absolute bottom-1.5 left-1.5 flex items-center gap-1">{bottomLeft}</div>}
      {duration !== undefined && (
        <span className={cx(CHIP, 'absolute bottom-1.5 right-1.5 font-cn-mono tabular-nums')}>
          <span aria-hidden>{formatTimecode(duration)}</span>
          <span className="sr-only">{spokenDuration(duration)}</span>
        </span>
      )}
    </div>
  );
}
