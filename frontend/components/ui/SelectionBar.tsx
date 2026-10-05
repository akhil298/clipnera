'use client';

import { X } from 'lucide-react';
import { type ReactNode, useEffect } from 'react';

import { cx } from '@/lib/design/styles';

import { Button } from './Button';
import { Kbd } from './Kbd';

export interface SelectionBarProps {
  /** Items selected; the bar hides at 0. */
  count: number;
  /** Noun for the count: "clip" → "3 clips selected". Default "item". */
  noun?: string;
  /** Actions for the selection (Add to project · Download · Delete). Buttons `size="sm"`. */
  children: ReactNode;
  /** "Select all", when not everything is selected. */
  onSelectAll?: () => void;
  /** Clears the selection; also bound to Escape while the bar shows. */
  onClear: () => void;
  /** `floating` sits fixed at the bottom centre (Library, Projects); `inline` sticks in the flow. */
  placement?: 'floating' | 'inline';
  className?: string;
}

/**
 * The multi-select toolbar (07 §5.5, 01 DS-13): "3 selected · actions · Clear
 * (Esc)". A labelled toolbar; the count is announced as it changes.
 */
export function SelectionBar({ count, noun = 'item', children, onSelectAll, onClear, placement = 'floating', className }: SelectionBarProps) {
  useEffect(() => {
    if (count === 0) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) onClear();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [count, onClear]);

  if (count === 0) return null;
  const label = `${count} ${noun}${count === 1 ? '' : 's'} selected`;
  return (
    <div
      role="toolbar"
      aria-label="Selection"
      className={cx(
        'flex max-w-full flex-wrap items-center gap-2 rounded-cn-xl border border-cn-border-strong bg-cn-surface-raised p-2 shadow-cn-2',
        'motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-cn-base',
        placement === 'floating' ? 'fixed inset-x-4 bottom-20 z-cn-sticky mx-auto w-fit md:bottom-6' : 'sticky bottom-4 z-cn-sticky',
        className,
      )}
    >
      <span role="status" className="px-2 font-cn-mono text-cn-label tabular-nums text-cn-fg">
        {label}
      </span>
      {onSelectAll && (
        <Button size="sm" variant="ghost" onClick={onSelectAll}>
          Select all
        </Button>
      )}
      <span aria-hidden className="mx-1 h-5 w-px bg-cn-border" />
      {children}
      <Button size="sm" variant="ghost" leadingIcon={<X />} onClick={onClear} trailingIcon={<Kbd keys={['Esc']} className="hidden sm:inline-flex" />}>
        Clear
      </Button>
    </div>
  );
}
