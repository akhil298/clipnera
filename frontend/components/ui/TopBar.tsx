import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

export interface TopBarProps {
  /** Left: menu button on phones, Wordmark, Breadcrumbs. */
  start?: ReactNode;
  /** Middle, takes the free space: the prompt entry, a page title. */
  children?: ReactNode;
  /** Right: activity, credits, notifications, AvatarMenu. Primary action last. */
  end?: ReactNode;
  /** Stick to the top of the scroll area. Default true. */
  sticky?: boolean;
  /** `editor` drops the gutter and border weight for the three-pane editor. */
  variant?: 'app' | 'editor';
  className?: string;
}

/**
 * The 48px header row of every signed-in screen (07 §5.2). Calm chrome:
 * solid page background (no glass, 07 §1), a hairline under it, `z-cn-sticky`.
 */
export function TopBar({ start, children, end, sticky = true, variant = 'app', className }: TopBarProps) {
  return (
    <header
      className={cx(
        'border-b border-cn-border bg-cn-bg',
        sticky && 'sticky top-0 z-cn-sticky',
        className,
      )}
    >
      <div className={cx('flex h-12 items-center gap-2', variant === 'app' ? 'px-4 sm:px-6 lg:px-8' : 'px-2 sm:px-3')}>
        {start && <div className="flex min-w-0 shrink items-center gap-2">{start}</div>}
        <div className="flex min-w-0 flex-1 items-center justify-center gap-2">{children}</div>
        {end && <div className="flex shrink-0 items-center gap-1 sm:gap-2">{end}</div>}
      </div>
    </header>
  );
}
