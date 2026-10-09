import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

/** A `dl` of read-only facts; label over value on phones (stand-in for DS-L4 KeyValues). */
export function KeyValues({ items, className }: { items: ReadonlyArray<{ label: string; value: ReactNode }>; className?: string }) {
  return (
    <dl className={cx('divide-y divide-cn-border text-cn-body', className)}>
      {items.map((item) => (
        <div key={item.label} className="flex flex-col gap-0.5 py-2 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <dt className="shrink-0 text-cn-fg-muted">{item.label}</dt>
          <dd className="min-w-0 break-words text-cn-fg sm:text-right">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
