'use client';

import React, { useEffect, useRef } from 'react';
import type { ViralClip } from '@/lib/types';

interface ReelsCoverPickerProps {
  clip: Pick<ViralClip, 'presignedUrl' | 'posterUrl' | 'duration' | 'title'>;
  /** Milliseconds into the clip, or undefined to let Instagram choose. */
  value: number | undefined;
  onChange: (value: number | undefined) => void;
}

const formatOffset = (ms: number) => {
  const total = ms / 1000;
  const minutes = Math.floor(total / 60);
  const seconds = (total % 60).toFixed(1).padStart(4, '0');
  return `${minutes}:${seconds}`;
};

/** The same frame at each crop Instagram shows a reel in. */
const CROPS = [
  { label: 'Reel', aspect: 'aspect-[9/16]', width: 'w-24 sm:w-28', overlay: true },
  { label: 'Feed', aspect: 'aspect-[4/5]', width: 'w-20 sm:w-24', overlay: false },
  { label: 'Profile grid', aspect: 'aspect-[3/4]', width: 'w-20 sm:w-24', overlay: false },
] as const;

/**
 * Picks the Reels cover: the frame people see in the profile grid and in
 * the feed before a reel plays. Without it Instagram takes a frame of its
 * own choosing, often mid-blink or mid-transition.
 */
export function ReelsCoverPicker({ clip, value, onChange }: ReelsCoverPickerProps) {
  const videoRefs = useRef<Array<HTMLVideoElement | null>>([]);
  const durationMs = Math.max(0, Math.round((clip.duration || 0) * 1000));
  const picking = value !== undefined;
  const canPick = Boolean(clip.presignedUrl) && durationMs > 0;

  // Every preview seeks to the chosen frame.
  useEffect(() => {
    if (value === undefined) return;
    videoRefs.current.forEach((video) => {
      if (!video) return;
      const seek = () => {
        video.currentTime = value / 1000;
      };
      if (video.readyState >= 1) seek();
      else video.addEventListener('loadedmetadata', seek, { once: true });
    });
  }, [value]);

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] font-bold text-neutral-300">Reels cover</span>
        <div className="inline-flex p-0.5 rounded-lg bg-neutral-900 border border-neutral-800" role="group" aria-label="Reels cover">
          <button
            type="button"
            onClick={() => onChange(undefined)}
            aria-pressed={!picking}
            className={`px-2.5 py-1 rounded-md text-[11px] font-semibold ${!picking ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}`}
          >
            Let Instagram choose
          </button>
          <button
            type="button"
            disabled={!canPick}
            onClick={() => onChange(Math.min(1000, durationMs))}
            aria-pressed={picking}
            title={canPick ? undefined : 'Available once the clip has finished rendering'}
            className={`px-2.5 py-1 rounded-md text-[11px] font-semibold disabled:opacity-40 ${picking ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}`}
          >
            Pick a frame
          </button>
        </div>
      </div>

      {!canPick && (
        <p className="text-[11px] text-neutral-500">You can pick a cover once the clip has finished rendering.</p>
      )}

      {picking && canPick && (
        <>
          <div className="flex items-end gap-3 overflow-x-auto pb-1">
            {CROPS.map((crop, i) => (
              <figure key={crop.label} className={`shrink-0 ${crop.width}`}>
                <div className={`relative ${crop.aspect} overflow-hidden rounded-lg bg-neutral-950 border border-neutral-800`}>
                  <video
                    ref={(el) => {
                      videoRefs.current[i] = el;
                    }}
                    src={clip.presignedUrl}
                    poster={clip.posterUrl || undefined}
                    muted
                    playsInline
                    preload="metadata"
                    className="absolute inset-0 h-full w-full object-cover"
                    aria-label={`${crop.label} preview of the cover frame`}
                  />
                  {crop.overlay && (
                    // Where Instagram draws the caption, handle and buttons.
                    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
                      <div className="absolute inset-x-0 bottom-0 h-[28%] bg-gradient-to-t from-black/70 to-transparent" />
                      <div className="absolute left-[6%] bottom-[6%] w-[55%] space-y-1">
                        <div className="h-1.5 w-2/3 rounded-full bg-white/70" />
                        <div className="h-1.5 w-full rounded-full bg-white/40" />
                      </div>
                      <div className="absolute right-[5%] bottom-[8%] flex flex-col gap-1.5">
                        {[0, 1, 2].map((dot) => (
                          <span key={dot} className="block h-2 w-2 rounded-full bg-white/70" />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <figcaption className="mt-1 text-center text-[10px] text-neutral-500">{crop.label}</figcaption>
              </figure>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <input
              id="reels-cover-offset"
              type="range"
              min={0}
              max={durationMs}
              step={100}
              value={value}
              onChange={(e) => onChange(Number(e.target.value))}
              className="flex-1 accent-amber-500"
              aria-label="Cover frame position"
              aria-valuetext={formatOffset(value)}
            />
            <span className="font-mono text-[11px] text-neutral-300 tabular-nums w-12 text-right">{formatOffset(value)}</span>
          </div>
          <p className="text-[10.5px] text-neutral-500">
            Keep faces and text inside the centre of the frame: the profile grid crops the top and bottom.
          </p>
        </>
      )}
    </div>
  );
}
