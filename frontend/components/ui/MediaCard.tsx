'use client';

import type { DragEvent, ReactNode } from 'react';

import { cx, focusWithinRing } from '@/lib/design/styles';

import { cardLinkOverlay } from './Card';
import { type ThumbAspect, VideoThumb } from './VideoThumb';

export interface MediaCardProps {
  title: string;
  /** Duration-first meta under the title: "Stock · 1080p" (the duration sits on the poster). */
  meta?: string;
  poster?: string;
  /** Muted proxy that plays after 150 ms of hover or focus (never under reduced motion). */
  previewSrc?: string;
  /** Seconds; shown in mono on the poster. */
  duration?: number;
  aspect?: ThumbAspect;
  selected?: boolean;
  /** Dimmed (hidden, dismissed). */
  dimmed?: boolean;
  /** The covering button. Give `href` instead to make the card a link. */
  onOpen?: () => void;
  href?: string;
  /** Accessible name of the covering control: "Use Coffee cup on a desk". Defaults to the title. */
  actionLabel?: string;
  /** On the poster: source icon (bottom-left), status (top-left), a ⋯ Menu (top-right; raise it with `relative z-cn-raised`). */
  bottomLeft?: ReactNode;
  topLeft?: ReactNode;
  topRight?: ReactNode;
  /** Writes a drag payload (B-roll onto the timeline). */
  onDragStart?: (event: DragEvent<HTMLDivElement>) => void;
  /** `sm` for 2-up panel grids. */
  size?: 'sm' | 'md';
  className?: string;
}

/**
 * A library, B-roll or clip tile (02 §5.4, 07 §5.5): chromeless poster with
 * hover preview and the media hairline, title and meta below. One button or
 * link covers the card.
 */
export function MediaCard({
  title,
  meta,
  poster,
  previewSrc,
  duration,
  aspect = '9:16',
  selected = false,
  dimmed = false,
  onOpen,
  href,
  actionLabel,
  bottomLeft,
  topLeft,
  topRight,
  onDragStart,
  size = 'md',
  className,
}: MediaCardProps) {
  const name = actionLabel ?? title;
  const titleText = <span className={cx('line-clamp-1 font-medium text-cn-fg', size === 'sm' ? 'text-cn-caption' : 'text-cn-label')}>{title}</span>;
  return (
    <div
      draggable={Boolean(onDragStart)}
      onDragStart={onDragStart}
      className={cx('group relative flex flex-col gap-1.5 rounded-cn-lg', focusWithinRing, className)}
    >
      <VideoThumb
        poster={poster}
        previewSrc={previewSrc}
        duration={duration}
        aspect={aspect}
        selected={selected}
        dimmed={dimmed}
        rounded="lg"
        topLeft={topLeft}
        topRight={topRight}
        bottomLeft={bottomLeft}
        className="cn-media-edge"
      />
      {href ? (
        <a href={href} aria-label={name} className={cx('text-left', cardLinkOverlay)}>
          {titleText}
        </a>
      ) : (
        <button type="button" onClick={onOpen} aria-label={name} className={cx('text-left', cardLinkOverlay)}>
          {titleText}
        </button>
      )}
      {meta && <span className="truncate text-cn-caption text-cn-fg-muted">{meta}</span>}
    </div>
  );
}
