import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

export interface EmptyStateProps {
  /** A lucide icon. Decorative. */
  icon?: ReactNode;
  /** What is empty, in plain words: "No projects yet". */
  title: ReactNode;
  /** Why, and what the user gets by acting. One or two sentences. */
  description?: ReactNode;
  /** The one next step, usually a primary Button. */
  action?: ReactNode;
  /** A quieter alternative, e.g. a link to help. */
  secondaryAction?: ReactNode;
  /** `compact` for panels and table bodies; `default` for whole pages. */
  size?: 'compact' | 'default';
  /** Heading level for the title; match the page outline. Default 2. */
  level?: 2 | 3 | 4;
  className?: string;
}

/** What a list, page or panel shows when there is nothing in it yet, or a search finds nothing. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  secondaryAction,
  size = 'default',
  level = 2,
  className,
}: EmptyStateProps) {
  const Heading = `h${level}` as const;
  const compact = size === 'compact';
  return (
    <div className={cx('flex flex-col items-center text-center', compact ? 'gap-2 px-4 py-6' : 'gap-3 px-6 py-12', className)}>
      {icon && (
        <span
          aria-hidden
          className={cx(
            'mb-1 inline-flex items-center justify-center rounded-cn-lg border border-cn-border bg-cn-surface text-cn-fg-secondary',
            compact ? 'size-9 [&_svg]:size-4' : 'size-12 [&_svg]:size-5',
          )}
        >
          {icon}
        </span>
      )}
      <Heading className={cx('font-semibold text-cn-fg', compact ? 'text-cn-body' : 'text-cn-title-sm')}>{title}</Heading>
      {description && (
        <p className={cx('max-w-sm text-cn-fg-secondary', compact ? 'text-cn-label' : 'text-cn-body')}>{description}</p>
      )}
      {(action || secondaryAction) && (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}
