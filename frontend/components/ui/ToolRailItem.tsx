'use client';

import type { ReactNode } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { Tooltip } from './Tooltip';

export interface ToolRailItemProps {
  label: string;
  icon: ReactNode;
  /** The tool's panel is open: `aria-pressed`, raised fill, amber icon. */
  active?: boolean;
  onClick: () => void;
  /** Something new inside (an AI cutaway, a failed item): a dot plus a spoken note. */
  badge?: string;
  /** Shortcut shown in the tooltip, e.g. "C". */
  shortcut?: string;
  /** `rail` stacks icon over label (48 px rail); `tab` is the phone's bottom row. */
  layout?: 'rail' | 'tab';
  disabled?: boolean;
}

/**
 * One tool in the editor's left rail (07 §5.4): Media, Captions, Brand, Music,
 * B-roll. A toggle button: pressing the open tool closes its panel. Wrap a set
 * in `<nav aria-label="Tools">`.
 */
export function ToolRailItem({ label, icon, active = false, onClick, badge, shortcut, layout = 'rail', disabled = false }: ToolRailItemProps) {
  const button = (
    <button
      type="button"
      aria-pressed={active}
      aria-keyshortcuts={shortcut}
      disabled={disabled}
      onClick={onClick}
      className={cx(
        'relative flex flex-col items-center justify-center gap-0.5 rounded-cn-md text-cn-caption transition-colors duration-cn-fast ease-cn-standard [&_svg]:size-4',
        layout === 'rail' ? 'w-12 py-1.5' : 'h-11 min-w-14 flex-1',
        active ? 'bg-cn-surface-active font-semibold text-cn-fg' : 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active',
        'disabled:pointer-events-none disabled:opacity-50',
        focusRing,
      )}
    >
      <span aria-hidden className={cx('relative inline-flex', active && 'text-cn-accent-text')}>
        {icon}
        {badge && <span className="absolute -right-1 -top-0.5 size-1.5 rounded-cn-full bg-cn-accent" />}
      </span>
      {label}
      {badge && <span className="sr-only">, {badge}</span>}
    </button>
  );
  return shortcut ? (
    <Tooltip content={`${label} · ${shortcut}`} side={layout === 'rail' ? 'right' : 'top'}>
      {button}
    </Tooltip>
  ) : (
    button
  );
}
