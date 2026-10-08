'use client';

import { Captions, CornerDownRight, Eye, Maximize, Pause, Play, ScanLine, UserRound, Volume2, VolumeX } from 'lucide-react';
import { type KeyboardEvent, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { IconButton } from '@/components/ui/IconButton';
import { QualityBadge } from '@/components/ui/QualityBadge';
import { cx, focusRing } from '@/lib/design/styles';

import { clock } from './sample';

const CAPTIONS = ['SO HERE IS', 'WHY WE PRICED', 'IT AT ₹499', 'A MONTH', 'LESS THAN', 'TWO COFFEES', 'AND PEOPLE', 'ACTUALLY STAY', 'FOR A YEAR'];

/** The picture: a neutral stand-in frame with the overlays the export burns in. */
export function Stage({
  time,
  captions,
  title,
  broll,
  safeZones = false,
  label,
  className,
}: {
  time: number;
  captions: boolean;
  title: string | null;
  broll: boolean;
  safeZones?: boolean;
  label?: string;
  className?: string;
}) {
  const line = CAPTIONS[Math.min(CAPTIONS.length - 1, Math.floor(time / 3.3))];
  const [first, ...rest] = line.split(' ');
  return (
    <div className={cx('relative aspect-[9/16] h-full max-h-full overflow-hidden rounded-cn-lg bg-gradient-to-b from-cn-surface-active to-cn-bg', className)}>
      {broll ? (
        <div className="absolute inset-0 bg-gradient-to-br from-cn-border-strong via-cn-surface-hover to-cn-surface">
          <span className="absolute bottom-1/3 left-3 rounded-cn-xs bg-cn-bg/80 px-1.5 text-cn-caption text-cn-fg-secondary">B-roll · Pouring coffee</span>
        </div>
      ) : (
        <UserRound aria-hidden className="absolute bottom-0 left-1/2 size-3/4 -translate-x-1/2 translate-y-[12%] text-cn-border-strong" strokeWidth={1} />
      )}
      {title && (
        <p className="absolute inset-x-[8%] top-[12%] rounded-cn-md bg-cn-fg px-3 py-2 text-center text-cn-label font-extrabold text-cn-bg">{title}</p>
      )}
      {captions && (
        <p className="absolute inset-x-0 bottom-[22%] text-center text-cn-title font-extrabold tracking-tight text-cn-fg [text-shadow:0_2px_8px_rgb(0_0_0/0.8)]">
          <span className="text-cn-accent">{first}</span> {rest.join(' ')}
        </p>
      )}
      {safeZones && (
        <>
          <span aria-hidden className="absolute inset-x-0 top-0 h-[13%] border-b border-dashed border-cn-danger/60 bg-cn-danger/10" />
          <span aria-hidden className="absolute inset-x-0 bottom-0 h-[20%] border-t border-dashed border-cn-danger/60 bg-cn-danger/10" />
          <span aria-hidden className="absolute bottom-[20%] right-0 top-[40%] w-[14%] border-l border-dashed border-cn-danger/60 bg-cn-danger/10" />
        </>
      )}
      {label && <span className="absolute right-2 top-2 rounded-cn-full bg-cn-bg/80 px-2 text-cn-caption font-semibold text-cn-fg-secondary">{label}</span>}
    </div>
  );
}

export interface PreviewPlayerProps {
  time: number;
  length: number;
  playing: boolean;
  onPlayPause: () => void;
  onSeek: (seconds: number) => void;
  quality: 'preview' | 'full';
  captions: boolean;
  title: string | null;
  broll: boolean;
  /** "Jump to change": shown when an edit landed away from the playhead (01 §6). */
  changedRange?: [number, number] | null;
  /** Read-only view of an earlier version. */
  viewing?: { name: string; onBack: () => void; onRestore: () => void } | null;
  compare?: 'off' | 'side';
  /** Clip state before the latest edit, for compare. */
  before?: { captions: boolean; title: string | null; broll: boolean; name: string };
  status?: 'ready' | 'loading' | 'error';
  compact?: boolean;
  className?: string;
}

/**
 * Design-system addition (02 §5.1): VideoPlayer chrome around the composed
 * proxy preview. Controls left to right: play, time, scrubber, mute,
 * captions, safe zones, full screen. Hold-to-compare and side-by-side live
 * here too.
 */
export function PreviewPlayer({
  time,
  length,
  playing,
  onPlayPause,
  onSeek,
  quality,
  captions,
  title,
  broll,
  changedRange,
  viewing,
  compare = 'off',
  before,
  status = 'ready',
  compact = false,
  className,
}: PreviewPlayerProps) {
  const [muted, setMuted] = useState(false);
  const [showCaptions, setShowCaptions] = useState(true);
  const [safeZones, setSafeZones] = useState(false);
  const [holding, setHolding] = useState(false);
  const outOfView = changedRange && (time < changedRange[0] - 1 || time > changedRange[1] + 1);

  const onScrubKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 5 : 1;
    const moves: Record<string, number> = { ArrowRight: time + step, ArrowLeft: time - step, Home: 0, End: length };
    if (event.key in moves) {
      event.preventDefault();
      onSeek(Math.max(0, Math.min(length, moves[event.key])));
    }
  };

  const showBefore = holding && before;
  const stageProps = showBefore
    ? { captions: before.captions && showCaptions, title: before.title, broll: before.broll }
    : { captions: captions && showCaptions, title, broll };

  return (
    <section aria-label="Preview" className={cx('relative flex min-h-0 flex-col bg-cn-bg', className)}>
      {viewing && (
        <div role="status" className="flex flex-wrap items-center gap-2 border-b border-cn-border bg-cn-accent-subtle px-3 py-2 text-cn-label text-cn-accent-text">
          <Eye aria-hidden className="size-4" />
          <span className="min-w-0 flex-1 truncate">
            Viewing an earlier version · <span className="font-semibold">{viewing.name}</span> · read-only
          </span>
          <Button size="sm" variant="secondary" onClick={viewing.onRestore}>
            Restore this version
          </Button>
          <Button size="sm" onClick={viewing.onBack}>
            Back to latest
          </Button>
        </div>
      )}

      <div className={cx('relative flex min-h-0 flex-1 items-center justify-center gap-4', compact ? 'p-2' : 'p-4')}>
        {status === 'loading' ? (
          <div role="status" className="flex aspect-[9/16] h-full items-center justify-center rounded-cn-lg bg-cn-surface text-cn-label">
            <span className="cn-shimmer-text">Loading preview</span>
          </div>
        ) : status === 'error' ? (
          <div role="alert" className="flex aspect-[9/16] h-full flex-col items-center justify-center gap-3 rounded-cn-lg bg-cn-surface p-4 text-center">
            <p className="text-cn-label text-cn-fg">This video could not play. Your edit is safe.</p>
            <Button size="sm" variant="secondary">
              Try again
            </Button>
          </div>
        ) : compare === 'side' && before ? (
          <>
            <figure className="flex h-full flex-col items-center gap-1.5">
              <Stage time={time} captions={before.captions} title={before.title} broll={before.broll} label="Before" className="h-[calc(100%-28px)]" />
              <figcaption className="text-cn-caption text-cn-fg-muted">{before.name}</figcaption>
            </figure>
            <figure className="flex h-full flex-col items-center gap-1.5">
              <Stage time={time} captions={captions} title={title} broll={broll} label="After" className="h-[calc(100%-28px)]" />
              <figcaption className="text-cn-caption text-cn-fg-muted">Latest</figcaption>
            </figure>
          </>
        ) : (
          <Stage time={time} {...stageProps} safeZones={safeZones} label={showBefore ? 'Before' : undefined} />
        )}
        <QualityBadge visible={quality === 'preview' && status === 'ready'} className="absolute left-4 top-4" />
        {outOfView && !viewing && (
          <Button
            size="sm"
            variant="secondary"
            leadingIcon={<CornerDownRight />}
            onClick={() => changedRange && onSeek(changedRange[0])}
            className="absolute bottom-3 left-1/2 -translate-x-1/2 shadow-cn-2"
          >
            Jump to change · {clock(changedRange[0])}
          </Button>
        )}
      </div>

      <div className={cx('flex shrink-0 items-center gap-1 border-t border-cn-border bg-cn-surface px-2', compact ? 'h-11' : 'h-10')}>
        <IconButton size="sm" label={playing ? 'Pause (Space)' : 'Play (Space)'} icon={playing ? <Pause /> : <Play />} onClick={onPlayPause} />
        <span className="w-20 shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary">
          {clock(time)} / {clock(length)}
        </span>
        <div
          role="slider"
          tabIndex={0}
          aria-label="Seek"
          aria-valuemin={0}
          aria-valuemax={Math.round(length)}
          aria-valuenow={Math.round(time)}
          aria-valuetext={`${clock(time)} of ${clock(length)}`}
          onKeyDown={onScrubKey}
          onPointerDown={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            onSeek(((event.clientX - rect.left) / rect.width) * length);
          }}
          className={cx('group relative h-6 min-w-0 flex-1 cursor-pointer rounded-cn-full', focusRing)}
        >
          <span className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-cn-full bg-cn-surface-active group-hover:h-1.5" />
          <span className="absolute left-0 top-1/2 h-1 -translate-y-1/2 rounded-cn-full bg-cn-accent group-hover:h-1.5" style={{ width: `${(time / length) * 100}%` }} />
        </div>
        {before && compare === 'off' && !compact && (
          <Button
            size="sm"
            variant="ghost"
            aria-pressed={holding}
            onPointerDown={() => setHolding(true)}
            onPointerUp={() => setHolding(false)}
            onPointerLeave={() => setHolding(false)}
            onKeyDown={(event) => event.key === ' ' && setHolding(true)}
            onKeyUp={() => setHolding(false)}
          >
            Hold to see before
          </Button>
        )}
        <IconButton size="sm" label={muted ? 'Unmute (M)' : 'Mute (M)'} pressed={muted} icon={muted ? <VolumeX /> : <Volume2 />} onClick={() => setMuted(!muted)} />
        <IconButton size="sm" label="Captions (C)" pressed={showCaptions} icon={<Captions />} onClick={() => setShowCaptions(!showCaptions)} />
        {!compact && <IconButton size="sm" label="Safe zones" pressed={safeZones} icon={<ScanLine />} onClick={() => setSafeZones(!safeZones)} />}
        <IconButton size="sm" label="Full screen (F)" icon={<Maximize />} />
      </div>
    </section>
  );
}
