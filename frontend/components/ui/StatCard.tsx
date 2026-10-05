import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

import { Skeleton, SkeletonGroup } from './Skeleton';

export interface StatDelta {
  /** "+12%", "−3". */
  value: string;
  direction: 'up' | 'down' | 'flat';
  /** Whether this change is good. Colours it emerald or rose; the arrow and words carry it too. */
  good?: boolean;
  /** "vs last week". */
  period?: string;
}

export interface StatCardProps {
  label: ReactNode;
  /** Pre-formatted: "1,240", "₹4,999", "3:42". `null` shows "—" with `emptyText`, never a fake number. */
  value: ReactNode | null;
  delta?: StatDelta;
  hint?: ReactNode;
  /** A Sparkline or other small figure under the number. */
  chart?: ReactNode;
  /** Highlight the one figure that matters most on the screen. */
  tone?: 'default' | 'accent';
  loading?: boolean;
  /** Why there is no value: "No views yet". */
  emptyText?: ReactNode;
  className?: string;
}

const ARROW = { up: <ArrowUpRight />, down: <ArrowDownRight />, flat: <ArrowRight /> } as const;
const SPOKEN = { up: 'up', down: 'down', flat: 'no change' } as const;

/** One headline number with its change and trend: analytics, admin overview, usage. */
export function StatCard({ label, value, delta, hint, chart, tone = 'default', loading = false, emptyText, className }: StatCardProps) {
  const frame = cx('flex flex-col gap-1 rounded-cn-lg border bg-cn-surface p-4', tone === 'accent' ? 'border-cn-accent-border' : 'border-cn-border', className);

  if (loading) {
    return (
      <SkeletonGroup label="Loading figure" className={frame}>
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="mt-1 h-7 w-1/2" />
        <Skeleton className="h-3 w-2/5" />
      </SkeletonGroup>
    );
  }

  const deltaTone = delta?.good === undefined || delta.direction === 'flat' ? 'text-cn-fg-secondary' : delta.good ? 'text-cn-success-text' : 'text-cn-danger-text';

  return (
    <div className={frame}>
      <p className="text-cn-caption text-cn-fg-muted">{label}</p>
      <p className="font-cn-mono text-cn-title font-semibold tabular-nums text-cn-fg">{value ?? '—'}</p>
      {value === null && emptyText && <p className="text-cn-caption text-cn-fg-muted">{emptyText}</p>}
      {delta && value !== null && (
        <p className={cx('inline-flex items-center gap-1 text-cn-caption font-semibold [&_svg]:size-3.5', deltaTone)}>
          <span aria-hidden className="inline-flex">
            {ARROW[delta.direction]}
          </span>
          <span className="sr-only">{SPOKEN[delta.direction]} </span>
          <span className="font-cn-mono tabular-nums">{delta.value}</span>
          {delta.period && <span className="font-normal text-cn-fg-muted">{delta.period}</span>}
        </p>
      )}
      {hint && <p className="text-cn-caption text-cn-fg-muted">{hint}</p>}
      {chart && value !== null && <div className="mt-2">{chart}</div>}
    </div>
  );
}
