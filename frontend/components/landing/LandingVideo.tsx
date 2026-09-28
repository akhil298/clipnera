'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { LANDING_CLIPS, type LandingClipKey } from '@/lib/landingMedia';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';

interface LandingVideoProps {
  clip: LandingClipKey;
  /** CSS object-position; picks which part of a 16:9 source a vertical crop shows. */
  position?: string;
  /** Must include a position (`relative` or `absolute`): the media and overlays are absolute inside it. */
  className?: string;
  mediaClassName?: string;
  children?: ReactNode;
}

/**
 * A muted looping clip over its poster frame. The poster is always rendered, so
 * the frame is never empty: the video fades in once it can play, pauses while
 * off screen, and is skipped entirely for reduced-motion visitors.
 */
export function LandingVideo({ clip, position = '50% 50%', className = '', mediaClassName = '', children }: LandingVideoProps) {
  const { poster, video, alt } = LANDING_CLIPS[clip];
  const videoRef = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const playVideo = !reducedMotion && !failed;

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !playVideo) return;
    const observer = new IntersectionObserver(
      ([entry]) => (entry.isIntersecting ? el.play().catch(() => undefined) : el.pause()),
      { threshold: 0.15 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [playVideo]);

  const media = `absolute inset-0 h-full w-full object-cover text-transparent ${mediaClassName}`;

  return (
    <div className={`overflow-hidden bg-neutral-900 ${className}`}>
      <img src={poster} alt={alt} loading="lazy" decoding="async" className={media} style={{ objectPosition: position }} />
      {playVideo && (
        <video
          ref={videoRef}
          src={video}
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden="true"
          onCanPlay={() => setReady(true)}
          onError={() => setFailed(true)}
          className={`${media} transition-opacity duration-500 ${ready ? 'opacity-100' : 'opacity-0'}`}
          style={{ objectPosition: position }}
        />
      )}
      {children}
    </div>
  );
}
