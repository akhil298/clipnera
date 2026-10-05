import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

interface SectionProps {
  id: string;
  title: ReactNode;
  /** One muted subline under the heading. */
  intro?: ReactNode;
  centred?: boolean;
  /** Width of the content column. */
  width?: 'wide' | 'narrow';
  className?: string;
  children: ReactNode;
}

/** A landing section: one `h2`, an optional subline, and the navbar-height scroll margin for anchor links. */
export function Section({ id, title, intro, centred = false, width = 'wide', className, children }: SectionProps) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className={cx('scroll-mt-16 py-24 lg:py-32', className)}>
      <div className={cx('mx-auto px-4 sm:px-8', width === 'wide' ? 'max-w-screen-xl' : 'max-w-3xl')}>
        <div className={cx('flex flex-col gap-3', centred && 'items-center text-center')}>
          <h2 id={`${id}-title`} className="max-w-3xl font-cn-sans text-cn-display-sm font-bold text-cn-fg sm:text-cn-display">
            {title}
          </h2>
          {intro && <p className="max-w-2xl text-cn-body-lg text-cn-fg-secondary">{intro}</p>}
        </div>
        <div className="mt-10 lg:mt-12">{children}</div>
      </div>
    </section>
  );
}
