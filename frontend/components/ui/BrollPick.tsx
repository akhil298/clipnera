'use client';

import { Search, Shuffle, Undo2 } from 'lucide-react';
import { useId, useState } from 'react';

import { cx } from '@/lib/design/styles';

import { Button } from './Button';
import { MediaCard } from './MediaCard';

export interface BrollShot {
  id: string;
  title: string;
  /** "Clipnera library", "Your uploads". */
  source: string;
  /** Seconds. */
  duration?: number;
  poster?: string;
  previewSrc?: string;
}

export interface BrollPickProps {
  /** The shot that was placed. */
  shot: BrollShot;
  /** Where it landed: "0:12–0:16". */
  range: string;
  /** Why it was chosen: "matches “coffee” and “pour”", "fits 9:16". */
  reasons: ReadonlyArray<string>;
  /** Up to four other shots that fit; Swap shows them. */
  alternates: ReadonlyArray<BrollShot>;
  /** One click swaps, as one new version. */
  onSwap: (shot: BrollShot) => void;
  onUndo?: () => void;
  /** Opens the B-roll panel prefilled with the search. */
  onSearchElse?: () => void;
  className?: string;
}

/**
 * "Chose this clip because…" under a run that placed B-roll (05-broll §8.3,
 * editor §9): where it landed, why, and a one-click Swap among alternates.
 */
export function BrollPick({ shot, range, reasons, alternates, onSwap, onUndo, onSearchElse, className }: BrollPickProps) {
  const id = useId();
  const [open, setOpen] = useState(false);

  return (
    <div className={cx('flex flex-col gap-2 rounded-cn-lg border border-cn-border bg-cn-surface p-2.5', className)}>
      <div className="flex items-start gap-2.5">
        <div className="cn-media-edge aspect-cn-portrait w-10 shrink-0 overflow-hidden rounded-cn-sm bg-cn-stage">
          {shot.poster && <img src={shot.poster} alt="" className="size-full object-cover" />}
        </div>
        <div className="min-w-0 space-y-0.5">
          <p className="text-cn-label text-cn-fg">
            Added at <span className="font-cn-mono tabular-nums">{range}</span> — “{shot.title}” <span className="text-cn-fg-muted">from {shot.source}</span>
          </p>
          {reasons.length > 0 && (
            <p className="text-cn-caption text-cn-fg-secondary">
              <span className="font-semibold">Why:</span> {reasons.join(' · ')}.
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {alternates.length > 0 && (
          <Button size="sm" variant="secondary" leadingIcon={<Shuffle />} aria-expanded={open} aria-controls={`${id}-alternates`} onClick={() => setOpen(!open)}>
            Swap
          </Button>
        )}
        {onSearchElse && (
          <Button size="sm" variant="ghost" leadingIcon={<Search />} onClick={onSearchElse}>
            Search for something else
          </Button>
        )}
        {onUndo && (
          <Button size="sm" variant="ghost" leadingIcon={<Undo2 />} onClick={onUndo}>
            Undo
          </Button>
        )}
      </div>
      {open && (
        <ul id={`${id}-alternates`} aria-label="Other shots that fit" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {alternates.map((alternate) => (
            <li key={alternate.id}>
              <MediaCard
                size="sm"
                title={alternate.title}
                meta={alternate.source}
                duration={alternate.duration}
                poster={alternate.poster}
                previewSrc={alternate.previewSrc}
                actionLabel={`Use ${alternate.title}`}
                onOpen={() => {
                  setOpen(false);
                  onSwap(alternate);
                }}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
