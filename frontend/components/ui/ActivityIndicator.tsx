'use client';

import type { ReactNode } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { Popover } from './Popover';
import { ProgressBar } from './ProgressBar';
import { WorkingText } from './WorkingText';

export interface ActivityItem {
  id: string;
  /** Project or file name: "Kavya on pricing". */
  title: string;
  /** The current step in plain words: "Burning in captions". */
  step: string;
  /** 0–100, only when the server sends it. */
  percent?: number;
  failed?: boolean;
  /** Link or button to the thing itself. */
  action?: ReactNode;
}

export interface ActivityIndicatorProps {
  items: ReadonlyArray<ActivityItem>;
  className?: string;
}

/**
 * Work running across projects (02 §4.8). Hidden when idle. A pill with a
 * live dot and a count opens a popover with each item's step; a failed item
 * turns the dot rose. Fed by `activity.updated` plus `GET /jobs?status=active`.
 */
export function ActivityIndicator({ items, className }: ActivityIndicatorProps) {
  if (items.length === 0) return null;
  const failed = items.filter((item) => item.failed).length;
  const name = `${items.length} in progress${failed ? `, ${failed} need${failed === 1 ? 's' : ''} a look` : ''}`;
  return (
    <Popover
      title="In progress"
      trigger={(props) => (
        <button
          type="button"
          {...props}
          aria-label={name}
          className={cx(
            'inline-flex h-8 items-center gap-1.5 rounded-cn-full border border-cn-border-strong bg-cn-surface px-2.5 font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary',
            'transition-colors duration-cn-fast hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active',
            focusRing,
            className,
          )}
        >
          <span aria-hidden className={cx('size-1.5 rounded-cn-full', failed ? 'bg-cn-danger' : 'bg-cn-accent motion-safe:animate-cn-pulse')} />
          {items.length}
        </button>
      )}
    >
      <ul className="flex flex-col gap-3">
        {items.map((item) => (
          <li key={item.id} className="flex flex-col gap-1">
            <p className="truncate text-cn-label font-semibold text-cn-fg">{item.title}</p>
            <p className="text-cn-caption">{item.failed ? <span className="text-cn-danger-text">{item.step}</span> : <WorkingText>{item.step}</WorkingText>}</p>
            {item.percent !== undefined && (
              <ProgressBar label={`${item.title}: ${item.step}`} value={item.percent} hideLabel size="sm" tone={item.failed ? 'danger' : 'accent'} />
            )}
            {item.action}
          </li>
        ))}
      </ul>
    </Popover>
  );
}
