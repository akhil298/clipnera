import { ChevronLeft, ChevronRight } from 'lucide-react';

import { cx, focusRing } from '@/lib/design/styles';

import { Button } from './Button';

export interface PaginationProps {
  /** 1-based. */
  page: number;
  /** Total pages when known. Omit for cursor-based lists (Previous/Next only). */
  pageCount?: number;
  /** Cursor lists: whether a next page exists. Ignored when `pageCount` is set. */
  hasNext?: boolean;
  onPageChange: (page: number) => void;
  /** "Payments pages". */
  label?: string;
  /** A page is loading: buttons stay put and ignore presses. */
  loading?: boolean;
  className?: string;
}

/** Page numbers to show: first, last, and a window round the current one, with gaps as `null`. */
export function pageWindow(page: number, count: number, siblings = 1): Array<number | null> {
  const pages = new Set([1, count]);
  for (let p = page - siblings; p <= page + siblings; p += 1) if (p >= 1 && p <= count) pages.add(p);
  const sorted = [...pages].sort((a, b) => a - b);
  return sorted.flatMap((p, index) => (index > 0 && p - sorted[index - 1] > 1 ? [null, p] : [p]));
}

/**
 * Previous / Next with page numbers between from `sm` up; phones show
 * "Page 2 of 9". For cursor-based APIs omit `pageCount` and pass `hasNext`.
 */
export function Pagination({ page, pageCount, hasNext, onPageChange, label = 'Pages', loading = false, className }: PaginationProps) {
  const canNext = pageCount !== undefined ? page < pageCount : Boolean(hasNext);
  const go = (to: number) => !loading && to !== page && onPageChange(to);

  return (
    <nav aria-label={label} aria-busy={loading || undefined} className={cx('flex items-center justify-between gap-2 sm:justify-center', className)}>
      <Button variant="ghost" size="sm" leadingIcon={<ChevronLeft />} disabled={page <= 1} onClick={() => go(page - 1)}>
        Previous
      </Button>
      {pageCount !== undefined && (
        <>
          <p className="text-cn-label text-cn-fg-secondary sm:hidden">
            Page <span className="font-cn-mono tabular-nums">{page}</span> of <span className="font-cn-mono tabular-nums">{pageCount}</span>
          </p>
          <ul className="hidden items-center gap-1 sm:flex">
            {pageWindow(page, pageCount).map((p, index) =>
              p === null ? (
                <li key={`gap-${index}`} aria-hidden className="px-1 text-cn-label text-cn-fg-muted">
                  …
                </li>
              ) : (
                <li key={p}>
                  <button
                    type="button"
                    aria-current={p === page ? 'page' : undefined}
                    aria-label={`Page ${p}`}
                    onClick={() => go(p)}
                    className={cx(
                      'inline-flex h-8 min-w-8 items-center justify-center rounded-cn-sm px-2 font-cn-mono text-cn-label tabular-nums transition-colors duration-cn-fast',
                      p === page ? 'bg-cn-surface-active font-semibold text-cn-fg' : 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active',
                      focusRing,
                    )}
                  >
                    {p}
                  </button>
                </li>
              ),
            )}
          </ul>
        </>
      )}
      <Button variant="ghost" size="sm" trailingIcon={<ChevronRight />} disabled={!canNext} loading={loading} onClick={() => go(page + 1)}>
        Next
      </Button>
    </nav>
  );
}
