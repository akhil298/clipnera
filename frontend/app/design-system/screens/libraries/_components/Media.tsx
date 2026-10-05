'use client';

import { Film, Heart, Lock, MoreHorizontal, Plus } from 'lucide-react';
import { type CSSProperties, type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { cardLinkOverlay } from '@/components/ui/Card';
import { Checkbox } from '@/components/ui/Checkbox';
import { IconButton } from '@/components/ui/IconButton';
import { Menu, type MenuEntry } from '@/components/ui/Menu';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusWithinRing } from '@/lib/design/styles';
import { delay } from '@/lib/design/tokens';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

import type { Look, Orientation } from './data';

export const RATIO: Record<Orientation, number> = { portrait: 9 / 16, square: 1, landscape: 16 / 9 };

/**
 * Stand-in for a poster frame: a simple painted scene from three colours.
 * Real tiles show the shot's thumbnail; this only gives the mockup footage
 * that is brighter than the chrome around it.
 */
export function Poster({ look, className, style }: { look: Look; className?: string; style?: CSSProperties }) {
  const [sky, mid, ground] = look;
  return (
    <div
      aria-hidden
      className={cx('relative overflow-hidden bg-cn-surface-active', className)}
      style={{ background: `linear-gradient(180deg, ${sky} 0%, ${sky} 45%, ${ground} 100%)`, ...style }}
    >
      <span className="absolute left-1/2 top-1/3 size-1/4 -translate-x-1/2 rounded-cn-full opacity-80 blur-sm" style={{ background: mid }} />
      <span className="absolute inset-x-0 bottom-0 h-1/3" style={{ background: `linear-gradient(180deg, transparent, ${ground})` }} />
    </div>
  );
}

export function DurationChip({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-cn-xs bg-cn-bg/80 px-1.5 py-0.5 font-cn-mono text-cn-caption tabular-nums text-cn-fg">{children}</span>
  );
}

export type TileStatus = 'live' | 'processing' | 'held' | 'failed' | 'retired' | 'missing' | 'locked';

export interface MediaCardProps {
  title: string;
  meta?: ReactNode;
  duration: string;
  look: Look;
  orientation: Orientation;
  status?: TileStatus;
  /** Step text while processing: "Finding shots". */
  step?: string;
  favourite?: boolean;
  onFavourite?: () => void;
  /** Shows the selection box (always while anything is selected, else on hover/focus). */
  selectable?: boolean;
  selected?: boolean;
  selectionActive?: boolean;
  onSelect?: () => void;
  /** The "+" quick action ("Add at playhead") in the editor panel. */
  onAdd?: () => void;
  badge?: ReactNode;
  menu?: ReadonlyArray<MenuEntry>;
  onOpen?: () => void;
  /** Roving focus from AssetGrid: the poster button's tab index. */
  tabIndex?: number;
  /** Inside an AssetGrid: small controls leave the tab order (keys reach them). */
  inGrid?: boolean;
  /** Fixed tile width instead of filling the grid cell (horizontal rows). */
  fixedWidth?: boolean;
}

/**
 * MediaCard (02 §5.4). One real button (the poster) opens details and covers
 * the card; checkbox, heart, add and menu sit above it. Inside an AssetGrid the
 * poster button is the roving tab stop and the small controls are reached by
 * keys (Space select, F favourite, A add, Shift+F10 menu), so a grid of 60
 * tiles is one Tab stop, not 240.
 */
export function MediaCard({
  title,
  meta,
  duration,
  look,
  orientation,
  status = 'live',
  step,
  favourite,
  onFavourite,
  selectable,
  selected,
  selectionActive,
  onSelect,
  onAdd,
  badge,
  menu,
  onOpen,
  tabIndex = 0,
  inGrid = false,
  fixedWidth,
}: MediaCardProps) {
  const reduced = useReducedMotion();
  const [previewing, setPreviewing] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const menuRef = useRef<HTMLDivElement>(null);
  const unusable = status === 'held' || status === 'failed' || status === 'missing' || status === 'processing';

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const startPreview = () => {
    if (reduced || unusable) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setPreviewing(true), delay.mediaHover);
  };
  const stopPreview = () => {
    window.clearTimeout(timer.current);
    setPreviewing(false);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === ' ' && selectable && onSelect) {
      event.preventDefault();
      onSelect();
    } else if (event.key.toLowerCase() === 'f' && onFavourite && !event.metaKey && !event.ctrlKey) {
      event.preventDefault();
      onFavourite();
    } else if (event.key.toLowerCase() === 'a' && onAdd && !event.metaKey && !event.ctrlKey) {
      event.preventDefault();
      onAdd();
    } else if ((event.key === 'F10' && event.shiftKey) || event.key === 'ContextMenu') {
      event.preventDefault();
      menuRef.current?.querySelector<HTMLButtonElement>('button')?.click();
    }
  };

  const showControls = cx('opacity-0 transition-opacity duration-cn-fast group-hover:opacity-100 group-focus-within:opacity-100');

  return (
    <div
      className={cx(
        'group relative flex flex-col gap-2 rounded-cn-lg p-1.5 transition-colors duration-cn-fast',
        selected ? 'bg-cn-accent-subtle outline outline-2 outline-cn-accent-border' : 'hover:bg-cn-surface-hover',
        focusWithinRing,
        fixedWidth && 'w-40 shrink-0',
      )}
      onPointerEnter={startPreview}
      onPointerLeave={stopPreview}
    >
      <div className="relative overflow-hidden rounded-cn-md" style={{ aspectRatio: String(RATIO[orientation]) }}>
        <Poster
          look={look}
          className={cx(
            'absolute inset-0 transition-[transform,opacity] duration-cn-fast ease-cn-out',
            previewing && 'scale-105',
            (unusable || status === 'retired') && 'opacity-50',
          )}
        />
        {previewing && (
          <span aria-hidden className="absolute inset-x-0 bottom-0 h-0.5 bg-cn-bg/40">
            <span className="block h-full w-2/5 bg-cn-accent motion-safe:animate-cn-sweep" />
          </span>
        )}
        {status === 'processing' && (
          <div className="absolute inset-x-2 bottom-2 space-y-1.5 rounded-cn-sm bg-cn-bg/80 p-2">
            <WorkingText className="text-cn-caption">{step ?? 'Preparing preview'}</WorkingText>
            <ProgressBar label={`${title}: ${step ?? 'preparing'}`} hideLabel size="sm" />
          </div>
        )}
        {status === 'missing' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-cn-surface p-2 text-center">
            <Film aria-hidden className="size-5 text-cn-fg-muted" />
            <span className="text-cn-caption text-cn-fg-secondary">Missing clip</span>
          </div>
        )}
        <div className="pointer-events-none absolute inset-x-1.5 top-1.5 flex items-start justify-between gap-1">
          <span className="pointer-events-auto relative z-cn-raised">
            {selectable && (
              <span className={cx('flex rounded-cn-xs bg-cn-bg/80 p-1', !selectionActive && !selected && showControls)}>
                <Checkbox
                  tabIndex={inGrid ? -1 : 0}
                  checked={!!selected}
                  onChange={() => onSelect?.()}
                  label={<span className="sr-only">Select {title}</span>}
                />
              </span>
            )}
          </span>
          <span className="flex flex-col items-end gap-1">
            {status === 'held' && <Badge tone="danger">Held for review</Badge>}
            {status === 'failed' && <Badge tone="danger">Failed</Badge>}
            {status === 'retired' && <Badge>No longer offered</Badge>}
            {status === 'locked' && (
              <Badge tone="accent" icon={<Lock />}>
                Pro
              </Badge>
            )}
            {badge}
          </span>
        </div>
        <div className="pointer-events-none absolute inset-x-1.5 bottom-1.5 flex items-end justify-between gap-1">
          <span className="pointer-events-auto relative z-cn-raised flex gap-1">
            {onFavourite && (
              <span className={cx(!favourite && showControls)}>
                <IconButton
                  size="sm"
                  variant="secondary"
                  tabIndex={inGrid ? -1 : 0}
                  label={favourite ? `Remove ${title} from favourites` : `Add ${title} to favourites`}
                  pressed={favourite}
                  icon={<Heart className={favourite ? 'fill-current' : undefined} />}
                  onClick={onFavourite}
                />
              </span>
            )}
            {onAdd && (
              <span className={showControls}>
                <IconButton size="sm" variant="primary" tabIndex={inGrid ? -1 : 0} label={`Add ${title} at playhead`} icon={<Plus />} onClick={onAdd} />
              </span>
            )}
          </span>
          {status !== 'processing' && status !== 'missing' && <DurationChip>{duration}</DurationChip>}
        </div>
      </div>
      <div className="flex items-start gap-1 px-0.5">
        <div className="min-w-0 flex-1">
          <button
            type="button"
            data-tile=""
            tabIndex={tabIndex}
            onClick={onOpen}
            onKeyDown={onKeyDown}
            onFocus={startPreview}
            onBlur={stopPreview}
            aria-describedby={inGrid ? 'asset-grid-keys' : undefined}
            className={cx('line-clamp-2 text-left text-cn-label font-semibold text-cn-fg', cardLinkOverlay, 'after:rounded-cn-lg')}
          >
            {title}
          </button>
          {meta && <p className="truncate text-cn-caption text-cn-fg-muted">{meta}</p>}
        </div>
        {menu && (
          <div ref={menuRef} className={cx('relative z-cn-raised -mr-1', showControls)}>
            <Menu
              align="end"
              items={menu}
              trigger={(props) => <IconButton {...props} tabIndex={inGrid ? -1 : 0} size="sm" label={`More for ${title}`} icon={<MoreHorizontal />} />}
            />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Justified rows: every tile keeps its own aspect ratio at one row height,
 * and rows fill the width (05 §3.2 "masonry keeps rows tidy"). One Tab stop;
 * arrows move by geometry, so they work at every width.
 */
export function AssetGrid({
  label,
  items,
  renderItem,
  rowHeight = 220,
}: {
  label: string;
  items: ReadonlyArray<{ id: string; orientation: Orientation }>;
  renderItem: (index: number, tabIndex: number) => ReactNode;
  rowHeight?: number;
}) {
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const onKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    const tiles = Array.from(listRef.current?.querySelectorAll<HTMLElement>('[data-tile]') ?? []);
    const index = tiles.indexOf(document.activeElement as HTMLElement);
    if (index < 0) return;
    let next = -1;
    if (event.key === 'ArrowRight') next = Math.min(index + 1, tiles.length - 1);
    else if (event.key === 'ArrowLeft') next = Math.max(index - 1, 0);
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tiles.length - 1;
    else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      const from = tiles[index].getBoundingClientRect();
      const down = event.key === 'ArrowDown';
      let best = Infinity;
      tiles.forEach((tile, i) => {
        const r = tile.getBoundingClientRect();
        const dy = down ? r.top - from.top : from.top - r.top;
        if (dy <= 4) return;
        const score = dy * 4 + Math.abs(r.left + r.width / 2 - (from.left + from.width / 2));
        if (score < best) {
          best = score;
          next = i;
        }
      });
    }
    if (next < 0 || next === index) return;
    event.preventDefault();
    setActive(next);
    tiles[next].focus();
  };

  return (
    <>
      <p id="asset-grid-keys" className="sr-only">
        Arrow keys move between clips. Enter opens details, F adds to favourites, Space selects, Shift F10 opens more actions.
      </p>
      <ul ref={listRef} aria-label={label} onKeyDown={onKeyDown} className="flex flex-wrap gap-2">
        {items.map((item, i) => {
          const ratio = RATIO[item.orientation];
          return (
            <li key={item.id} style={{ flexGrow: ratio * 100, flexBasis: `${ratio * rowHeight}px`, maxWidth: `${ratio * rowHeight * 1.6}px` }}>
              {renderItem(i, i === active ? 0 : -1)}
            </li>
          );
        })}
        <li aria-hidden style={{ flexGrow: 100 }} />
      </ul>
    </>
  );
}

/** Horizontal row of fixed-width tiles (featured collections). Scrolls on its own; never the page. */
export function TileRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <ul aria-label={label} className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
      {children}
    </ul>
  );
}
