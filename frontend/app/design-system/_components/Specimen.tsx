import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

/** One top-level gallery section with an anchor for the side navigation. */
export function GallerySection({ id, title, intro, children }: { id: string; title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20 space-y-6 border-t border-cn-border pt-10 first:border-t-0 first:pt-0">
      <div className="space-y-1">
        <h2 id={`${id}-title`} className="text-cn-title-lg font-bold text-cn-fg">
          {title}
        </h2>
        {intro && <p className="max-w-2xl text-cn-body text-cn-fg-secondary">{intro}</p>}
      </div>
      {children}
    </section>
  );
}

/** One component, shown in its states. */
export function Specimen({ title, note, children, className }: { title: string; note?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className="space-y-3">
      <div className="space-y-0.5">
        <h3 className="text-cn-title-sm font-semibold text-cn-fg">{title}</h3>
        {note && <p className="text-cn-label text-cn-fg-muted">{note}</p>}
      </div>
      <div className={cx('rounded-cn-xl border border-cn-border bg-cn-bg p-5', className)}>{children}</div>
    </div>
  );
}

/** A labelled cell inside a specimen: "Disabled", "Loading", … */
export function State({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={cx('flex min-w-0 flex-col items-start gap-2', className)}>
      <span className="font-cn-mono text-cn-caption text-cn-fg-muted">{label}</span>
      {children}
    </div>
  );
}

export function StateGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 lg:grid-cols-4', className)}>{children}</div>;
}
