"use client";
import React, { useCallback, useRef, useState } from 'react';
import {
  Calendar,
  Check,
  Copy,
  Download,
  Loader2,
  Pause,
  Play,
  Scissors,
} from 'lucide-react';
import { ViralClip } from '@/lib/types';
import { ClipPoster } from './ClipPoster';

interface ClipCardProps {
  clip: ViralClip;
  index: number;
  isSelected: boolean;
  isExporting: boolean;
  onSelect: (clip: ViralClip) => void;
  onEdit: (clip: ViralClip) => void;
  onSchedule: (clip: ViralClip) => void;
  onExport: (clip: ViralClip) => void;
}

function formatTimecode(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds || 0));
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  return `${minutes}:${String(rest).padStart(2, '0')}`;
}

/** Amber above 85, neutral below, so the eye finds the strong clips first. */
function scoreTone(score: number): { ring: string; text: string; chip: string } {
  if (score >= 85) {
    return {
      ring: 'stroke-amber-400',
      text: 'text-amber-300',
      chip: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    };
  }
  if (score >= 70) {
    return {
      ring: 'stroke-emerald-400',
      text: 'text-emerald-300',
      chip: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25',
    };
  }
  return {
    ring: 'stroke-neutral-500',
    text: 'text-neutral-300',
    chip: 'bg-neutral-800 text-neutral-300 border-neutral-700',
  };
}

// Only one card plays with sound at a time; starting another pauses this one.
let audibleVideo: HTMLVideoElement | null = null;

const RADIUS = 15;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export const ClipCard: React.FC<ClipCardProps> = ({
  clip,
  index,
  isSelected,
  isExporting,
  onSelect,
  onEdit,
  onSchedule,
  onExport,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [withSound, setWithSound] = useState(false);
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);

  const tone = scoreTone(clip.viralityScore);
  const hasVideo = Boolean(clip.presignedUrl) && !failed;

  const togglePlay = useCallback(
    (event: React.MouseEvent) => {
      event.stopPropagation();
      const video = videoRef.current;
      if (!video) return;
      // A muted hover preview counts as "not playing" here: the click is a
      // request to actually watch, with sound.
      if (video.paused || video.muted) {
        if (audibleVideo && audibleVideo !== video) audibleVideo.pause();
        audibleVideo = video;
        video.muted = false;
        setWithSound(true);
        // A play() rejection (autoplay policy, expired URL) must not leave the
        // button stuck showing "pause".
        video.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
      } else {
        video.pause();
      }
    },
    [],
  );

  // Hovering scrubs a muted preview, the way every short-form tool behaves;
  // leaving rewinds so the next hover starts from the hook again.
  const handleMouseEnter = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.paused) return;
    video.play().then(() => setIsPlaying(true)).catch(() => undefined);
  }, []);

  const handleMouseLeave = useCallback(() => {
    const video = videoRef.current;
    // A clip the user chose to watch keeps playing; only the preview stops.
    if (!video || !video.muted) return;
    video.pause();
    video.currentTime = 0;
    setIsPlaying(false);
  }, []);

  const handleCopyHook = useCallback(
    (event: React.MouseEvent) => {
      event.stopPropagation();
      navigator.clipboard.writeText(clip.hook || clip.title);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    },
    [clip.hook, clip.title],
  );

  return (
    <article
      onClick={() => onSelect(clip)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border bg-neutral-900 transition-all duration-200 cursor-pointer ${
        isSelected
          ? 'border-amber-500/70 ring-1 ring-amber-500/30 shadow-lg shadow-amber-500/5'
          : 'border-neutral-800 hover:border-neutral-700 hover:shadow-lg hover:shadow-black/40'
      }`}
    >
      {/* Vertical preview */}
      <div className="relative aspect-[9/16] w-full overflow-hidden bg-black">
        {hasVideo ? (
          <video
            ref={videoRef}
            src={clip.presignedUrl}
            poster={clip.posterUrl || undefined}
            muted
            loop
            playsInline
            preload="metadata"
            className="h-full w-full object-cover"
            onPlay={() => setIsPlaying(true)}
            onPause={(event) => {
              // Back to silent preview mode, so the next hover stays muted.
              event.currentTarget.muted = true;
              if (audibleVideo === event.currentTarget) audibleVideo = null;
              setWithSound(false);
              setIsPlaying(false);
            }}
            onError={() => {
              setFailed(true);
              setIsPlaying(false);
            }}
          />
        ) : (
          <ClipPoster
            clip={clip}
            className="h-full"
            pendingLabel={failed ? 'Preview link expired. Refresh to load it again.' : 'Rendering…'}
          />
        )}

        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-black/50" />

        {/* Rank + score dial */}
        <div className="absolute left-2.5 top-2.5 flex items-center gap-2">
          <span className="rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10px] font-bold text-neutral-200 backdrop-blur-sm">
            #{index + 1}
          </span>
        </div>

        <div className="absolute right-2.5 top-2.5">
          <div className="relative h-9 w-9">
            <svg viewBox="0 0 36 36" className="h-9 w-9 -rotate-90">
              <circle cx="18" cy="18" r={RADIUS} fill="rgba(0,0,0,0.65)" stroke="rgba(255,255,255,0.12)" strokeWidth="3" />
              <circle
                cx="18"
                cy="18"
                r={RADIUS}
                fill="none"
                strokeWidth="3"
                strokeLinecap="round"
                className={tone.ring}
                strokeDasharray={CIRCUMFERENCE}
                strokeDashoffset={CIRCUMFERENCE * (1 - Math.min(100, Math.max(0, clip.viralityScore)) / 100)}
              />
            </svg>
            <span
              className={`absolute inset-0 flex items-center justify-center font-mono text-[11px] font-black ${tone.text}`}
            >
              {clip.viralityScore}
            </span>
          </div>
        </div>

        {/* Play control */}
        {hasVideo && (
          <button
            onClick={togglePlay}
            aria-label={isPlaying && withSound ? 'Pause clip' : 'Play clip with sound'}
            className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100 focus:outline-none"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm transition-transform active:scale-90">
              {isPlaying && withSound ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 fill-current" />}
            </span>
          </button>
        )}

        {/* Timeline position + duration */}
        <div className="absolute bottom-2.5 left-2.5 right-2.5 flex items-center justify-between">
          <span className="rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-neutral-300 backdrop-blur-sm">
            {formatTimecode(clip.startTime)}–{formatTimecode(clip.endTime)}
          </span>
          <span className="rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-white backdrop-blur-sm">
            {clip.duration}s
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col gap-2.5 p-3.5">
        <h3 className="line-clamp-2 text-sm font-bold leading-snug text-white" title={clip.title}>
          {clip.title}
        </h3>

        {clip.hook && (
          <div className="flex items-start justify-between gap-2 rounded-lg border border-neutral-800/80 bg-neutral-950 px-2.5 py-2">
            <p className="line-clamp-2 text-[11px] italic leading-relaxed text-neutral-300" title={clip.hook}>
              {clip.hook}
            </p>
            <button
              onClick={handleCopyHook}
              title="Copy hook"
              className="shrink-0 rounded p-0.5 text-neutral-500 transition-colors hover:text-white"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>
        )}

        {/* Score breakdown */}
        <div className="grid grid-cols-2 gap-2">
          {([
            { label: 'Hook', value: clip.hookScore, bar: 'bg-amber-400' },
            { label: 'Engage', value: clip.engagementScore, bar: 'bg-emerald-400' },
          ] as const).map((metric) => (
            <div key={metric.label} className="space-y-1">
              <div className="flex items-baseline justify-between">
                <span className="text-[10px] font-medium uppercase tracking-wide text-neutral-500">
                  {metric.label}
                </span>
                <span className="font-mono text-[10px] font-semibold text-neutral-300">{metric.value}</span>
              </div>
              <div className="h-1 w-full overflow-hidden rounded-full bg-neutral-800">
                <div
                  className={`h-full rounded-full ${metric.bar}`}
                  style={{ width: `${Math.min(100, Math.max(0, metric.value))}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="mt-auto flex items-center gap-1.5 pt-1">
          <button
            onClick={(event) => {
              event.stopPropagation();
              onEdit(clip);
            }}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-[11px] font-semibold text-white transition-colors hover:bg-neutral-700"
          >
            <Scissors className="h-3.5 w-3.5" />
            <span>Edit</span>
          </button>
          <button
            onClick={(event) => {
              event.stopPropagation();
              onSchedule(clip);
            }}
            title="Schedule post"
            className="rounded-lg border border-neutral-700 bg-neutral-800 p-1.5 text-amber-400 transition-colors hover:bg-neutral-700"
          >
            <Calendar className="h-4 w-4" />
          </button>
          <button
            onClick={(event) => {
              event.stopPropagation();
              onExport(clip);
            }}
            disabled={isExporting || !clip.presignedUrl}
            title={clip.presignedUrl ? 'Download clip' : 'Not ready to download yet'}
            className="rounded-lg border border-neutral-700 bg-neutral-800 p-1.5 text-neutral-300 transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </article>
  );
};
