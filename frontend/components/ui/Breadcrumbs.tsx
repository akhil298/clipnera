import Link from 'next/link';
import { ChevronLeft } from 'lucide-react';

import { cx, focusRing } from '@/lib/design/styles';

export interface Crumb {
  label: string;
  /** Omit for the current page (always the last crumb). */
  href?: string;
}

export interface BreadcrumbsProps {
  items: ReadonlyArray<Crumb>;
  className?: string;
}

const linkClass = cx('truncate rounded-cn-xs text-cn-fg-secondary transition-colors duration-cn-fast hover:text-cn-fg', focusRing);

/**
 * Where this page sits: Projects / Episode 12 / Clips. Long labels truncate.
 * On phones only a back link to the parent shows, to keep the bar to one line.
 */
export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  const parent = [...items.slice(0, -1)].reverse().find((item) => item.href);
  return (
    <nav aria-label="Breadcrumb" className={cx('min-w-0', className)}>
      {parent?.href && (
        <Link href={parent.href} className={cx('inline-flex max-w-full items-center gap-1 text-cn-label sm:hidden', linkClass)}>
          <ChevronLeft aria-hidden className="size-4 shrink-0" />
          <span className="truncate">{parent.label}</span>
        </Link>
      )}
      <ol className={cx('min-w-0 items-center gap-1.5 text-cn-label', parent ? 'hidden sm:flex' : 'flex')}>
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} className={cx('flex min-w-0 items-center gap-1.5', !last && 'max-w-48')}>
              {index > 0 && (
                <span aria-hidden className="text-cn-fg-disabled">
                  /
                </span>
              )}
              {last || !item.href ? (
                <span aria-current={last ? 'page' : undefined} className={cx('truncate', last ? 'font-semibold text-cn-fg' : 'text-cn-fg-secondary')}>
                  {item.label}
                </span>
              ) : (
                <Link href={item.href} className={linkClass}>
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
