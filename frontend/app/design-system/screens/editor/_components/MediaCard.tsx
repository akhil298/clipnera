'use client';

import { Film } from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState } from 'react';

import { cx } from '@/lib/design/styles';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

import { POSTER_TONES } from './sample';

const HOVER_DELAY_MS = 150;

/**
 * A neutral poster stand-in (no external images in the mockups). Real
 * screens show the poster, then the proxy on hover.
 */
export function Poster({ tone, aspect = '9:16', className, children }: { tone: number; aspect?: '9:16' | '16:9' | '1:1'; className?: string; children?: ReactNode }) {
  const ratio = aspect === '9:16' ? 'aspect-[9/16]' : aspect === '16:9' ? 'aspect-video' : 'aspect-square';
  return (
    <div className={cx('relative overflow-hidden bg-gradient-to-b', POSTER_TONES[tone % POSTER_TONES.length], ratio, className)}>
      <Film aria-hidden className="absolute left-1/2 top-1/2 size-6 -translate-x-1/2 -translate-y-1/2 text-cn-fg-disabled" />
      {children}
    </div>
  );
}

/**
 * Hover preview, as specified for MediaCard (02 §5.4): preload on approach,
 * play muted after 150 ms of hover or keyboard focus, stop on leave, never
 * under reduced motion. Here "playing" is drawn as a moving progress line.
 */
export function useHoverPreview() {
  const reduced = useReducedMotion();
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const begin = () => {
    if (reduced) return;
    timer.current = setTimeout(() => setPlaying(true), HOVER_DELAY_MS);
  };
  const end = () => {
    if (timer.current) clearTimeout(timer.current);
    setPlaying(false);
  };
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  return {
    playing,
    handlers: { onPointerEnter: begin, onPointerLeave: end, onFocus: begin, onBlur: end },
  };
}

export function PreviewSweep({ playing }: { playing: boolean }) {
  if (!playing) return null;
  return (
    <span aria-hidden className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-cn-overlay/40">
      <span className="absolute inset-y-0 left-0 w-2/5 bg-cn-fg/80 motion-safe:animate-cn-sweep" />
    </span>
  );
}
