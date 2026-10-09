import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

/**
 * One settings group (DS-L6, local until promoted): an `h2`, an optional
 * description and actions, then the content.
 */
export function SettingsCard({
  id,
  title,
  description,
  actions,
  children,
  className,
}: {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  const headingId = `${id}-title`;
  return (
    <section id={id} aria-labelledby={headingId} className={cx('rounded-cn-lg border border-cn-border bg-cn-surface p-4 sm:p-6', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h2 id={headingId} className="text-cn-title-sm font-semibold text-cn-fg">
            {title}
          </h2>
          {description && <p className="max-w-xl text-cn-body text-cn-fg-secondary">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
      </div>
      {children && <div className="mt-5">{children}</div>}
    </section>
  );
}
