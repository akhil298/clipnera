'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { Volume2, VolumeX } from 'lucide-react';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';

interface LoopVideoProps {
  src: string;
  poster: string;
  label: string;
  /** Must include a position (`relative` or `absolute`); overlays sit inside it. */
  className?: string;
  videoClassName?: string;
  /** When given, a sound button is shown; only one video should have sound at a time. */
  sound?: { on: boolean; onToggle: () => void };
  children?: ReactNode;
}

/**
 * A real clip that loops muted while on screen. Turning sound on restarts it
 * from the top; reduced-motion visitors see the poster until they ask for sound.
 */
export function LoopVideo({ src, poster, label, className = '', videoClassName = '', sound, children }: LoopVideoProps) {
  const ref = useRef<HTMLVideoElement>(null);
  const reducedMotion = usePrefersReducedMotion();
  const soundOn = sound?.on ?? false;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.muted = !soundOn;
    if (soundOn) {
      el.currentTime = 0;
      el.play().catch(() => undefined);
      return;
    }
    if (reducedMotion) {
      el.pause();
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => (entry.isIntersecting ? el.play().catch(() => undefined) : el.pause()),
      { threshold: 0.2 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [soundOn, reducedMotion]);

  return (
    <div className={`overflow-hidden border border-neutral-800 bg-neutral-900 ${className}`}>
      <video
        ref={ref}
        src={src}
        poster={poster}
        muted
        loop
        playsInline
        preload="metadata"
        aria-label={label}
        className={`absolute inset-0 h-full w-full object-cover ${videoClassName}`}
      />
      {children}
      {sound && (
        <button
          type="button"
          onClick={sound.onToggle}
          aria-pressed={soundOn}
          className={`absolute bottom-2.5 right-2.5 z-10 flex h-11 items-center gap-1.5 rounded-full px-3.5 text-[13px] font-bold transition-colors ${
            soundOn ? 'bg-amber-500 text-neutral-950' : 'bg-neutral-950/80 text-white hover:bg-neutral-950'
          }`}
        >
          {soundOn ? <Volume2 className="h-4 w-4" aria-hidden="true" /> : <VolumeX className="h-4 w-4" aria-hidden="true" />}
          {soundOn ? 'Sound on' : 'Tap for sound'}
        </button>
      )}
    </div>
  );
}
