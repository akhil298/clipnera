"use client";
import React, { useState } from 'react';
import { Sparkles } from 'lucide-react';
import type { ViralClip } from '@/lib/types';

interface ClipPosterProps {
  clip: Pick<ViralClip, 'title' | 'posterUrl' | 'presignedUrl'>;
  /** 9/16 for shorts and reels; other ratios crop the same frame. */
  aspect?: '9/16' | '3/4' | '4/5' | '1/1';
  className?: string;
  /** Text under the icon when there is neither a poster nor a video yet. */
  pendingLabel?: string;
  children?: React.ReactNode;
}

const ASPECT_CLASS: Record<NonNullable<ClipPosterProps['aspect']>, string> = {
  '9/16': 'aspect-[9/16]',
  '3/4': 'aspect-[3/4]',
  '4/5': 'aspect-[4/5]',
  '1/1': 'aspect-square',
};

/**
 * A clip's still: the poster frame the backend renders, falling back to the
 * video's first frame, then to a rendering placeholder. Clips used to show a
 * black box whenever the video URL was missing, even with a poster on hand.
 */
export const ClipPoster: React.FC<ClipPosterProps> = ({
  clip,
  aspect = '9/16',
  className = '',
  pendingLabel = 'Rendering…',
  children,
}) => {
  const [posterFailed, setPosterFailed] = useState(false);
  const poster = !posterFailed && clip.posterUrl ? clip.posterUrl : '';

  return (
    <div className={`relative w-full overflow-hidden bg-neutral-950 ${ASPECT_CLASS[aspect]} ${className}`}>
      {poster ? (
        <img
          src={poster}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setPosterFailed(true)}
          className="absolute inset-0 h-full w-full object-cover"
        />
      ) : clip.presignedUrl ? (
        // #t=0.1 asks the browser for the first real frame instead of a blank.
        <video
          src={`${clip.presignedUrl}#t=0.1`}
          muted
          playsInline
          preload="metadata"
          className="absolute inset-0 h-full w-full object-cover"
          aria-hidden="true"
        />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[linear-gradient(110deg,#141416_30%,#1d1d21_50%,#141416_70%)] bg-[length:200%_100%] animate-[skeleton-shimmer_1.8s_ease-in-out_infinite]">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-neutral-800/80">
            <Sparkles className="h-4 w-4 text-neutral-400" />
          </span>
          <span className="px-3 text-center text-[11px] text-neutral-400">{pendingLabel}</span>
        </div>
      )}
      {children}
    </div>
  );
};
