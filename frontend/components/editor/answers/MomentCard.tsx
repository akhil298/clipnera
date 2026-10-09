'use client';

import { CircleAlert, CircleCheck, Plus, RotateCcw, Shuffle, Trash2, Undo2 } from 'lucide-react';

import { Badge, Button, IconButton, VideoThumb, cardLinkOverlay } from '@/components/ui';
import { cx, focusWithinRing } from '@/lib/design/styles';
import { formatTimecode, spokenDuration } from '@/lib/design/timecode';

export type MomentCardState = 'streaming' | 'rest' | 'selected' | 'on_timeline' | 'dismissed' | 'failed';

export interface MomentCardProps {
  /** What was said there (a moment) or what the shot shows (B-roll). */
  quote: string;
  /** B-roll titles are not speech, so they are not put in quotes. */
  quoted?: boolean;
  /** One of the 11 content formats, or the B-roll source ("Archival"). Always neutral. */
  tag?: string;
  /** Seconds into the source. */
  start: number;
  duration?: number;
  /** Only when the backend scored it. */
  score?: number;
  poster?: string;
  /** Muted preview played on hover after 150 ms. */
  previewSrc?: string;
  /** Output shape: 9:16 at 56 px, 16:9 at 96 px. */
  aspect?: '9:16' | '16:9';
  /** Source length in seconds: draws the 4 px source bar with this moment's tick. */
  sourceDuration?: number;
  state?: MomentCardState;
  /** `on_timeline`: where it landed on the timeline, in seconds. */
  placedAt?: number;
  /** `failed`: why it could not be cut. */
  failReason?: string;
  /** Click the card: seek the preview to `start`. */
  onSeek: () => void;
  /** "Use this": becomes a Moment chip in the composer. */
  onUse?: () => void;
  onSwap?: () => void;
  onRemove?: () => void;
  /** `dismissed`: bring it back. */
  onRestore?: () => void;
  /** `failed`: try cutting it again. */
  onRetry?: () => void;
  className?: string;
}

/**
 * A candidate clip shown as a quote (07 §6.4), and the frame B-roll results reuse. States: streaming
 * in, rest, selected, on the timeline (Swap / Remove), dismissed (Undo) and failed to cut (Try again).
 */
export function MomentCard({
  quote,
  quoted = true,
  tag,
  start,
  duration,
  score,
  poster,
  previewSrc,
  aspect = '9:16',
  sourceDuration,
  state = 'rest',
  placedAt,
  failReason,
  onSeek,
  onUse,
  onSwap,
  onRemove,
  onRestore,
  onRetry,
  className,
}: MomentCardProps) {
  const text = quoted ? `“${quote}”` : quote;
  const dismissed = state === 'dismissed';
  return (
    <div
      className={cx(
        'relative flex gap-3 rounded-cn-lg border bg-cn-surface p-3 transition-colors duration-cn-fast',
        state === 'selected' ? 'border-2 border-cn-accent-border' : 'border-cn-border',
        !dismissed && 'hover:bg-cn-surface-hover active:bg-cn-surface-active',
        state === 'streaming' && 'cn-pending-sheen',
        focusWithinRing,
        className,
      )}
    >
      <VideoThumb
        poster={poster}
        previewSrc={dismissed ? undefined : previewSrc}
        aspect={aspect}
        dimmed={dismissed}
        rounded="md"
        className={cx('shrink-0 self-start', aspect === '9:16' ? 'w-14' : 'w-24')}
      />
      <div className={cx('flex min-w-0 flex-1 flex-col gap-1.5', dismissed && 'opacity-50')}>
        <button
          type="button"
          onClick={onSeek}
          aria-label={`Play from ${spokenDuration(start)}: ${quote}`}
          className={cx('text-left', cardLinkOverlay)}
        >
          <span className="line-clamp-3 text-cn-body text-cn-fg">{text}</span>
        </button>
        <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-cn-caption text-cn-fg-muted">
          {tag && <Badge>{tag}</Badge>}
          <span className="font-cn-mono tabular-nums">{formatTimecode(start, { total: sourceDuration })}</span>
          {duration !== undefined && (
            <>
              <span aria-hidden>·</span>
              <span className="font-cn-mono tabular-nums">{formatTimecode(duration)}</span>
            </>
          )}
          {score !== undefined && <span className="ml-auto font-cn-mono tabular-nums text-cn-fg-secondary">Score {score}</span>}
        </p>
        {sourceDuration !== undefined && sourceDuration > 0 && <SourceBar start={start} duration={duration} total={sourceDuration} />}
        <StateFooter
          state={state}
          placedAt={placedAt}
          failReason={failReason}
          onSwap={onSwap}
          onRemove={onRemove}
          onRestore={onRestore}
          onRetry={onRetry}
        />
      </div>
      {onUse && (state === 'rest' || state === 'selected') && (
        <IconButton
          size="sm"
          label={`Use the moment at ${spokenDuration(start)} in the prompt`}
          icon={<Plus />}
          pressed={state === 'selected'}
          onClick={onUse}
          className="relative z-cn-raised -mr-1 -mt-1 shrink-0"
        />
      )}
    </div>
  );
}

/** A 4 px track over the whole source, an amber tick at the moment and an amber span for its length. */
function SourceBar({ start, duration = 0, total }: { start: number; duration?: number; total: number }) {
  const at = Math.min(100, (start / total) * 100);
  const width = Math.min(100 - at, (duration / total) * 100);
  return (
    <div aria-hidden className="relative h-1 w-full rounded-cn-full bg-cn-surface-active">
      <span className="absolute inset-y-0 rounded-cn-full bg-cn-accent/30" style={{ left: `${at}%`, width: `${width}%` }} />
      <span className="absolute -inset-y-0.5 w-0.5 rounded-cn-full bg-cn-accent" style={{ left: `${at}%` }} />
    </div>
  );
}

function StateFooter({
  state,
  placedAt,
  failReason,
  onSwap,
  onRemove,
  onRestore,
  onRetry,
}: Pick<MomentCardProps, 'state' | 'placedAt' | 'failReason' | 'onSwap' | 'onRemove' | 'onRestore' | 'onRetry'>) {
  if (state === 'on_timeline') {
    return (
      <div className="relative z-cn-raised flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 text-cn-caption text-cn-success-text [&_svg]:size-3.5">
          <CircleCheck aria-hidden />
          {placedAt !== undefined ? (
            <>
              On timeline at <span className="font-cn-mono tabular-nums">{formatTimecode(placedAt)}</span>
            </>
          ) : (
            'On timeline'
          )}
        </span>
        {onSwap && (
          <Button size="sm" variant="ghost" leadingIcon={<Shuffle />} onClick={onSwap}>
            Swap
          </Button>
        )}
        {onRemove && (
          <Button size="sm" variant="ghost" leadingIcon={<Trash2 />} onClick={onRemove}>
            Remove
          </Button>
        )}
      </div>
    );
  }
  if (state === 'dismissed') {
    return (
      <p className="relative z-cn-raised flex items-center gap-2 text-cn-caption text-cn-fg-muted">
        Hidden
        {onRestore && (
          <Button size="sm" variant="ghost" leadingIcon={<Undo2 />} onClick={onRestore}>
            Undo
          </Button>
        )}
      </p>
    );
  }
  if (state === 'failed') {
    return (
      <div className="relative z-cn-raised flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 text-cn-caption text-cn-danger-text [&_svg]:size-3.5">
          <CircleAlert aria-hidden />
          {failReason ?? 'Couldn’t cut this moment.'}
        </span>
        {onRetry && (
          <Button size="sm" variant="secondary" leadingIcon={<RotateCcw />} onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    );
  }
  return null;
}
