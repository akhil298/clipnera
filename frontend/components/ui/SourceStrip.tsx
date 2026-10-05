'use client';

import { Plus } from 'lucide-react';
import { useState } from 'react';

import { cx, focusRing, focusWithinRing } from '@/lib/design/styles';
import { formatTimecode, spokenDuration } from '@/lib/design/timecode';

import { cardLinkOverlay } from './Card';
import { IconButton } from './IconButton';

export interface Moment {
  id: string;
  /** The quoted line: what was said there. */
  quote: string;
  /** Seconds into the source. */
  start: number;
  /** Length in seconds, when known. */
  duration?: number;
  /** Content format, a neutral tag: "Story", "Hot take". */
  tag?: string;
  /** Only when the backend scored it (07 §1 rule 4). */
  score?: number;
  poster?: string;
  /** Still arriving (`run.finding` streaming): pending sheen. */
  pending?: boolean;
}

export interface SourceStripProps {
  moments: ReadonlyArray<Moment>;
  /** Click a card: seek the preview to its start. */
  onSeek: (moment: Moment) => void;
  /** "Use this": attach it as a Moment ContextChip. */
  onUse?: (moment: Moment) => void;
  /** Cards before "+N". Default 4. */
  maxVisible?: number;
  label?: string;
  className?: string;
}

/**
 * Moments a reply cites or a run found, above the prose (07 §6.3): a strip of
 * compact moment cards plus "+N" that scrolls on its own row, never the page.
 */
export function SourceStrip({ moments, onSeek, onUse, maxVisible = 4, label = 'Moments', className }: SourceStripProps) {
  const [expanded, setExpanded] = useState(false);
  if (moments.length === 0) return null;
  const shown = expanded ? moments : moments.slice(0, maxVisible);
  const hidden = moments.length - shown.length;
  return (
    <section aria-label={label} className={cx('min-w-0', className)}>
      <ul className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1 [mask-image:linear-gradient(90deg,black_90%,transparent)]">
        {shown.map((moment) => (
          <li key={moment.id} className="snap-start">
            <MomentChipCard moment={moment} onSeek={onSeek} onUse={onUse} />
          </li>
        ))}
        {hidden > 0 && (
          <li className="snap-start">
            <button
              type="button"
              onClick={() => setExpanded(true)}
              aria-label={`Show ${hidden} more moments`}
              className={cx(
                'flex h-full min-h-16 w-14 items-center justify-center rounded-cn-lg border border-dashed border-cn-border-strong font-cn-mono text-cn-label text-cn-fg-secondary',
                'transition-colors duration-cn-fast hover:bg-cn-surface-hover hover:text-cn-fg',
                focusRing,
              )}
            >
              +{hidden}
            </button>
          </li>
        )}
      </ul>
    </section>
  );
}

function MomentChipCard({ moment, onSeek, onUse }: { moment: Moment; onSeek: SourceStripProps['onSeek']; onUse?: SourceStripProps['onUse'] }) {
  const { quote, start, duration, tag, score, poster, pending } = moment;
  return (
    <div
      className={cx(
        'relative flex w-56 gap-2 rounded-cn-lg border border-cn-border bg-cn-surface p-2 transition-colors duration-cn-fast',
        'hover:bg-cn-surface-hover active:bg-cn-surface-active',
        pending && 'cn-pending-sheen',
        focusWithinRing,
      )}
    >
      <div className="cn-media-edge aspect-cn-portrait w-8 shrink-0 overflow-hidden rounded-cn-xs bg-cn-stage">
        {poster && <img src={poster} alt="" className="size-full object-cover" />}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <button type="button" onClick={() => onSeek(moment)} aria-label={`Play from ${spokenDuration(start)}: ${quote}`} className={cx('text-left', cardLinkOverlay)}>
          <span className="line-clamp-2 text-cn-label text-cn-fg">“{quote}”</span>
        </button>
        <p className="flex items-center gap-1 text-cn-caption text-cn-fg-muted">
          {tag && <span className="truncate">{tag}</span>}
          {tag && <span aria-hidden>·</span>}
          <span className="font-cn-mono tabular-nums">{formatTimecode(start)}</span>
          {duration !== undefined && <span className="font-cn-mono tabular-nums">· {formatTimecode(duration)}</span>}
          {score !== undefined && <span className="ml-auto font-cn-mono tabular-nums text-cn-fg-secondary">{score}</span>}
        </p>
      </div>
      {onUse && (
        <IconButton size="sm" label={`Use the moment at ${spokenDuration(start)} in the prompt`} icon={<Plus />} className="relative z-cn-raised -mr-1 -mt-1" onClick={() => onUse(moment)} />
      )}
    </div>
  );
}
