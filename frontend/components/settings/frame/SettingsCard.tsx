import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

export interface SettingsCardProps {
  /** Becomes the `id` of the section, so search results and links can jump to it. */
  id: string;
  title: ReactNode;
  description?: ReactNode;
  /** Buttons on the right of the heading; they wrap under it on phones. */
  actions?: ReactNode;
  /** Destructive group (delete account, delete workspace): rose edge, always last on the page. */
  danger?: boolean;
  children?: ReactNode;
  className?: string;
}

/**
 * One settings group (07 §5.6, stand-in for DS-L6 until the design system promotes it):
 * `surface`, `rounded-cn-lg`, an h2, and rows divided by hairlines.
 */
export function SettingsCard({ id, title, description, actions, danger = false, children, className }: SettingsCardProps) {
  const headingId = `${id}-title`;
  return (
    <section
      id={id}
      aria-labelledby={headingId}
      className={cx(
        'scroll-mt-20 rounded-cn-lg border bg-cn-surface p-4 sm:p-6',
        danger ? 'border-cn-danger/50' : 'border-cn-border',
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <h2 id={headingId} className="text-cn-title-sm font-semibold text-cn-fg">
            {title}
          </h2>
          {description && <p className="max-w-xl text-cn-body text-cn-fg-secondary">{description}</p>}
        </div>
        {actions && <div className="flex w-full shrink-0 flex-wrap gap-2 sm:w-auto">{actions}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </section>
  );
}

/**
 * A row inside a card: label and description on the left, the control on the right,
 * at least 56 px tall. On phones the control drops under the text.
 */
export function SettingsRow({ label, description, control }: { label: ReactNode; description?: ReactNode; control?: ReactNode }) {
  return (
    <div className="flex min-h-14 flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0">
        <p className="text-cn-label font-semibold text-cn-fg">{label}</p>
        {description && <p className="text-cn-caption text-cn-fg-secondary">{description}</p>}
      </div>
      {control && <div className="shrink-0">{control}</div>}
    </div>
  );
}
