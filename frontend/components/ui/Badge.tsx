import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

export type BadgeTone = 'neutral' | 'accent' | 'success' | 'danger' | 'info';

const TONE: Record<BadgeTone, { badge: string; dot: string }> = {
  neutral: { badge: 'bg-cn-surface-hover text-cn-fg-secondary border-cn-border-strong', dot: 'bg-cn-fg-muted' },
  accent: { badge: 'bg-cn-accent-subtle text-cn-accent-text border-cn-accent/30', dot: 'bg-cn-accent' },
  success: { badge: 'bg-cn-success-subtle text-cn-success-text border-cn-success/30', dot: 'bg-cn-success' },
  danger: { badge: 'bg-cn-danger-subtle text-cn-danger-text border-cn-danger/30', dot: 'bg-cn-danger' },
  info: { badge: 'bg-cn-info-subtle text-cn-info-text border-cn-info/30', dot: 'bg-cn-info' },
};

export interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  icon?: ReactNode;
  /** A leading dot. Colour is never the only signal: the text carries the meaning. */
  dot?: boolean;
  /** Pulse the dot for live work. Holds still under reduced motion. */
  pulse?: boolean;
  className?: string;
}

/** A short, static label: plan name, count, "New", "Preview quality". Not interactive. */
export function Badge({ tone = 'neutral', children, icon, dot = false, pulse = false, className }: BadgeProps) {
  return (
    <span
      className={cx(
        'inline-flex h-5 max-w-full items-center gap-1 whitespace-nowrap rounded-cn-full border px-2 text-cn-caption font-semibold [&_svg]:size-3',
        TONE[tone].badge,
        className,
      )}
    >
      {dot && (
        <span
          aria-hidden
          className={cx('size-1.5 shrink-0 rounded-cn-full', TONE[tone].dot, pulse && 'motion-safe:animate-cn-pulse')}
        />
      )}
      {icon && (
        <span aria-hidden className="inline-flex">
          {icon}
        </span>
      )}
      <span className="truncate">{children}</span>
    </span>
  );
}

export type Status = 'processing' | 'ready' | 'failed' | 'scheduled' | 'paused' | 'draft';

const STATUS: Record<Status, { tone: BadgeTone; label: string }> = {
  processing: { tone: 'accent', label: 'Processing' },
  ready: { tone: 'success', label: 'Ready' },
  failed: { tone: 'danger', label: 'Failed' },
  scheduled: { tone: 'info', label: 'Scheduled' },
  paused: { tone: 'neutral', label: 'Paused' },
  draft: { tone: 'neutral', label: 'Draft' },
};

/**
 * The one status language: a dot plus a word, same colour meaning everywhere.
 * Successor to `StatusPill` (its violet `ai` tone is retired; use `accent`).
 */
export function StatusBadge({ status, children, className }: { status: Status; children?: ReactNode; className?: string }) {
  const { tone, label } = STATUS[status];
  return (
    <Badge tone={tone} dot pulse={status === 'processing'} className={className}>
      {children ?? label}
    </Badge>
  );
}
