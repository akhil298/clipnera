'use client';

import { MomentCard } from './MomentCard';

/**
 * One B-roll shot a run placed. Built by E4a from the run's B-roll findings (`run.finding` with
 * `kind: 'broll'`) and the item ids its operations touched.
 */
export interface BrollPlacement {
  /** Timeline item id of the placed shot. */
  itemId: string;
  /** What the shot shows: "Welder at work". */
  title: string;
  /** "Archival", "Your uploads". */
  source: string;
  /** Shot length in seconds. */
  duration: number;
  /** Where it landed on the timeline, in seconds. */
  placedAt: number;
  poster?: string;
  previewSrc?: string;
  /** Output shape of the project. */
  aspect?: '9:16' | '16:9';
}

export interface BrollResultCardProps {
  placement: BrollPlacement;
  /** Seek the preview to where the shot landed. */
  onSeek: (seconds: number) => void;
  /** Opens the alternates (B1's BrollPick swap in the B-roll panel). */
  onSwap?: (placement: BrollPlacement) => void;
  onRemove?: (placement: BrollPlacement) => void;
  className?: string;
}

/** "Welder at work · Archival · 0:08 · On timeline at 0:14", with Swap and Remove (07 §6.4). */
export function BrollResultCard({ placement, onSeek, onSwap, onRemove, className }: BrollResultCardProps) {
  return (
    <MomentCard
      quote={placement.title}
      quoted={false}
      tag={placement.source}
      start={placement.placedAt}
      duration={placement.duration}
      poster={placement.poster}
      previewSrc={placement.previewSrc}
      aspect={placement.aspect}
      state="on_timeline"
      placedAt={placement.placedAt}
      onSeek={() => onSeek(placement.placedAt)}
      onSwap={onSwap && (() => onSwap(placement))}
      onRemove={onRemove && (() => onRemove(placement))}
      className={className}
    />
  );
}
