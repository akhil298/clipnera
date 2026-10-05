'use client';

import type { KeyboardEvent, ReactNode } from 'react';

import { getTabbables } from '@/lib/design/focus';
import { cx } from '@/lib/design/styles';

import { Skeleton, SkeletonGroup } from './Skeleton';
import { ASPECT_CLASS, type ThumbAspect } from './VideoThumb';

const COLUMNS: Record<ThumbAspect, string> = {
  '9:16': 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6',
  '1:1': 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5',
  '16:9': 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
};

export interface MediaGridProps<T> {
  /** Accessible name of the list: "Clips", "Your uploads". */
  label: string;
  items: ReadonlyArray<T>;
  getKey: (item: T) => string;
  renderItem: (item: T, index: number) => ReactNode;
  /** Sets the column count: portrait tiles pack tighter than landscape. */
  aspect?: ThumbAspect;
  /** Shows skeleton tiles inside one live region instead of the items. */
  loading?: boolean;
  skeletonCount?: number;
  /** Shown when not loading and there are no items (an EmptyState, compact). */
  empty?: ReactNode;
  className?: string;
}

const MOVES: Record<string, (index: number, columns: number) => number> = {
  ArrowRight: (index) => index + 1,
  ArrowLeft: (index) => index - 1,
  ArrowDown: (index, columns) => index + columns,
  ArrowUp: (index, columns) => index - columns,
};

/**
 * A responsive grid of media tiles (clips, library shots, uploads). Each tile
 * keeps its own tab stop; arrow keys also move between tiles, by row and
 * column, so long grids are quick to cross by keyboard.
 */
export function MediaGrid<T>({
  label,
  items,
  getKey,
  renderItem,
  aspect = '9:16',
  loading = false,
  skeletonCount = 8,
  empty,
  className,
}: MediaGridProps<T>) {
  const grid = cx('grid gap-3 sm:gap-4', COLUMNS[aspect], className);

  if (loading) {
    return (
      <SkeletonGroup label={`Loading ${label.toLowerCase()}`} className={grid}>
        {Array.from({ length: skeletonCount }, (_, index) => (
          <div key={index} className="flex flex-col gap-2">
            <Skeleton className={ASPECT_CLASS[aspect]} />
            <Skeleton className="h-3 w-3/4" />
          </div>
        ))}
      </SkeletonGroup>
    );
  }

  if (items.length === 0) return <>{empty}</>;

  const onKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    const move = MOVES[event.key];
    const target = event.target as HTMLElement;
    if (!move || target.matches('input, textarea, [role="slider"]')) return;
    const tiles = Array.from(event.currentTarget.children) as HTMLElement[];
    const index = tiles.findIndex((tile) => tile.contains(target));
    if (index < 0) return;
    const columns = getComputedStyle(event.currentTarget).gridTemplateColumns.split(' ').length;
    const next = tiles[move(index, columns)];
    if (!next) return;
    event.preventDefault();
    getTabbables(next)[0]?.focus();
  };

  return (
    <ul aria-label={label} onKeyDown={onKeyDown} className={grid}>
      {items.map((item, index) => (
        <li key={getKey(item)} className="min-w-0">
          {renderItem(item, index)}
        </li>
      ))}
    </ul>
  );
}
