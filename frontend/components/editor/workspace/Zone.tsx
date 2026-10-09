import type { ReactNode } from 'react';

import { EmptyState } from '@/components/ui/EmptyState';
import { cx } from '@/lib/design/styles';

/** One editor zone: a `surface` panel with `rounded-cn-lg` on the 4 px `bg` gutter (07 §5.4). `stage` is the black footage well. */
export function ZoneSurface({ label, tone = 'surface', className, children }: { label: string; tone?: 'surface' | 'stage'; className?: string; children: ReactNode }) {
  return (
    <section
      aria-label={label}
      className={cx('relative flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-cn-lg', tone === 'stage' ? 'bg-cn-stage' : 'bg-cn-surface', className)}
    >
      {children}
    </section>
  );
}

/** The calm body a zone shows before its unit fills it. */
export function ZoneNote({ icon, title, description }: { icon: ReactNode; title: string; description?: string }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto">
      <EmptyState size="compact" level={3} icon={icon} title={title} description={description} />
    </div>
  );
}
