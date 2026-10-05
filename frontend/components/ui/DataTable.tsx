'use client';

import { useVirtualizer } from '@tanstack/react-virtual';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { type ReactNode, useRef } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { Checkbox } from './Checkbox';
import { Skeleton } from './Skeleton';

export type SortDirection = 'ascending' | 'descending';
export interface SortState {
  key: string;
  direction: SortDirection;
}

export interface DataTableColumn<R> {
  key: string;
  header: string;
  render: (row: R) => ReactNode;
  /** Right-aligned mono tabular figures. */
  numeric?: boolean;
  /** The header becomes a sort button with `aria-sort`. */
  sortable?: boolean;
  /** Header kept for screen readers only (action columns). */
  hideHeader?: boolean;
  /** The card title on phones. One column per table. */
  primary?: boolean;
  /** Leave this column out of the phone card (secondary detail). */
  hideOnMobile?: boolean;
  /** Width and other cell classes, e.g. `w-32`. */
  className?: string;
}

export interface DataTableProps<R> {
  /** What the table lists. Read first by screen readers; `hideCaption` keeps it visual-only off. */
  caption: string;
  hideCaption?: boolean;
  columns: ReadonlyArray<DataTableColumn<R>>;
  rows: ReadonlyArray<R>;
  getRowId: (row: R) => string;
  /** Names a row for its select box: "Select payment pay_123". */
  getRowLabel?: (row: R) => string;
  sort?: SortState | null;
  onSortChange?: (sort: SortState) => void;
  /** Turns on the checkbox column (with an indeterminate select-all). */
  selectedIds?: ReadonlySet<string>;
  onSelectionChange?: (ids: ReadonlySet<string>) => void;
  loading?: boolean;
  /** Skeleton rows while loading. Default 5. */
  loadingRows?: number;
  /** Shown in place of the body when there are no rows: a compact EmptyState. */
  empty?: ReactNode;
  /** Highlight a row (the one open in a side panel). */
  activeId?: string;
  /**
   * Render only the rows in view (@tanstack/react-virtual) inside a scrolling
   * body. For long admin lists; rows should keep the 44px height. Phone cards
   * are not virtualised, so pair long lists with Pagination there.
   */
  virtualize?: boolean;
  /** Height cap of the scrolling body when virtualised. Default `max-h-96`. */
  scrollClassName?: string;
  className?: string;
}

const ROW_HEIGHT = 44;

/**
 * Admin lists, payments, usage, team (02 §3.18). A semantic table from `md`
 * up with a sticky header; stacked cards on phones, never a sideways-scrolling
 * table. Sorting and selection are controlled, so the server can own them.
 * Whole-row links: render a link with `cardLinkOverlay` in the primary cell.
 * Long lists: `virtualize`, or Pagination for server-paged data.
 */
export function DataTable<R>({
  caption,
  hideCaption = true,
  columns,
  rows,
  getRowId,
  getRowLabel,
  sort,
  onSortChange,
  selectedIds,
  onSelectionChange,
  loading = false,
  loadingRows = 5,
  empty,
  activeId,
  virtualize = false,
  scrollClassName = 'max-h-96',
  className,
}: DataTableProps<R>) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: virtualize && !loading ? rows.length : 0,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });
  const windowed = virtualize ? virtualizer.getVirtualItems() : null;
  const visibleRows = windowed ? windowed.map((item) => rows[item.index]) : rows;
  const padTop = windowed?.[0]?.start ?? 0;
  const padBottom = windowed && windowed.length > 0 ? virtualizer.getTotalSize() - windowed[windowed.length - 1].end : 0;
  const selectable = selectedIds !== undefined && onSelectionChange !== undefined;
  const ids = rows.map(getRowId);
  const selectedCount = selectable ? ids.filter((id) => selectedIds.has(id)).length : 0;
  const all = selectable && rows.length > 0 && selectedCount === rows.length;
  const some = selectedCount > 0 && !all;
  const span = columns.length + (selectable ? 1 : 0);

  const toggle = (id: string) => {
    if (!selectable) return;
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectionChange(next);
  };
  const toggleAll = () => {
    if (!selectable) return;
    const next = new Set(selectedIds);
    for (const id of ids) {
      if (all) next.delete(id);
      else next.add(id);
    }
    onSelectionChange(next);
  };

  const sortBy = (key: string) =>
    onSortChange?.({ key, direction: sort?.key === key && sort.direction === 'ascending' ? 'descending' : 'ascending' });

  const rowLabel = (row: R) => getRowLabel?.(row) ?? `row ${getRowId(row)}`;
  const showEmpty = !loading && rows.length === 0;

  const header = (column: DataTableColumn<R>) => {
    if (column.hideHeader) return <span className="sr-only">{column.header}</span>;
    if (!column.sortable || !onSortChange) return column.header;
    const active = sort?.key === column.key;
    const Icon = !active ? ArrowUpDown : sort.direction === 'ascending' ? ArrowUp : ArrowDown;
    return (
      <button
        type="button"
        onClick={() => sortBy(column.key)}
        className={cx(
          'inline-flex items-center gap-1 rounded-cn-xs hover:text-cn-fg',
          active && 'text-cn-fg',
          column.numeric && 'flex-row-reverse',
          focusRing,
        )}
      >
        {column.header}
        <Icon aria-hidden className={cx('size-3', !active && 'opacity-50')} />
      </button>
    );
  };

  return (
    <div className={className}>
      <div ref={scrollRef} className={cx('hidden md:block', virtualize && cx('overflow-y-auto', scrollClassName))}>
      <table className="w-full border-collapse text-left">
        <caption className={cx('pb-2 text-left text-cn-label text-cn-fg-muted', hideCaption && 'sr-only')}>{caption}</caption>
        <thead className="sticky top-0 z-cn-raised bg-cn-bg">
          <tr className="h-9 border-b border-cn-border">
            {selectable && (
              <th scope="col" className="w-10 px-3">
                <Checkbox
                  checked={all}
                  indeterminate={some}
                  disabled={loading || rows.length === 0}
                  onChange={toggleAll}
                  label={<span className="sr-only">Select all rows</span>}
                />
              </th>
            )}
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                aria-sort={column.sortable ? (sort?.key === column.key ? sort.direction : 'none') : undefined}
                className={cx('px-3 text-cn-caption font-medium text-cn-fg-muted', column.numeric && 'text-right', column.className)}
              >
                {header(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading &&
            Array.from({ length: loadingRows }, (_, index) => (
              <tr key={`loading-${index}`} aria-hidden className="h-11 border-b border-cn-border">
                {Array.from({ length: span }, (_, cell) => (
                  <td key={cell} className="px-3">
                    <Skeleton className={cx('h-3', cell === 0 && selectable ? 'w-4' : 'w-3/4')} />
                  </td>
                ))}
              </tr>
            ))}
          {showEmpty && (
            <tr>
              <td colSpan={span}>{empty}</td>
            </tr>
          )}
          {padTop > 0 && <tr aria-hidden style={{ height: padTop }} />}
          {!loading &&
            visibleRows.map((row) => {
              const id = getRowId(row);
              const isSelected = selectable && selectedIds.has(id);
              return (
                <tr
                  key={id}
                  aria-current={activeId === id || undefined}
                  className={cx(
                    'relative h-11 border-b border-cn-border text-cn-body text-cn-fg transition-colors duration-cn-fast',
                    isSelected || activeId === id ? 'bg-cn-accent-subtle' : 'hover:bg-cn-surface-hover',
                    'focus-within:bg-cn-surface-hover',
                  )}
                >
                  {selectable && (
                    <td className="w-10 px-3">
                      <Checkbox
                        className="relative z-cn-raised"
                        checked={isSelected}
                        onChange={() => toggle(id)}
                        label={<span className="sr-only">Select {rowLabel(row)}</span>}
                      />
                    </td>
                  )}
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cx('px-3 py-2 align-middle', column.numeric && 'text-right font-cn-mono tabular-nums', column.className)}
                    >
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          {padBottom > 0 && <tr aria-hidden style={{ height: padBottom }} />}
        </tbody>
      </table>
      </div>

      <div className="md:hidden">
        {loading ? (
          <div aria-hidden className="space-y-2">
            {Array.from({ length: Math.min(loadingRows, 3) }, (_, index) => (
              <Skeleton key={index} className="h-24 rounded-cn-lg" />
            ))}
          </div>
        ) : showEmpty ? (
          empty
        ) : (
          <ul aria-label={caption} className="space-y-2">
            {rows.map((row) => {
              const id = getRowId(row);
              const isSelected = selectable && selectedIds.has(id);
              return (
                <li
                  key={id}
                  className={cx(
                    'relative flex gap-3 rounded-cn-lg border p-3',
                    isSelected || activeId === id ? 'border-cn-accent-border bg-cn-accent-subtle' : 'border-cn-border bg-cn-surface',
                  )}
                >
                  {selectable && (
                    <Checkbox
                      className="relative z-cn-raised"
                      checked={isSelected}
                      onChange={() => toggle(id)}
                      label={<span className="sr-only">Select {rowLabel(row)}</span>}
                    />
                  )}
                  <dl className="min-w-0 flex-1 space-y-1.5">
                    {columns
                      .filter((column) => !column.hideOnMobile)
                      .map((column) =>
                        column.primary ? (
                          <div key={column.key} className="text-cn-body font-semibold text-cn-fg">
                            <dt className="sr-only">{column.header}</dt>
                            <dd>{column.render(row)}</dd>
                          </div>
                        ) : (
                          <div key={column.key} className="flex items-start justify-between gap-3 text-cn-label">
                            <dt className={cx('text-cn-fg-muted', column.hideHeader && 'sr-only')}>{column.header}</dt>
                            <dd className={cx('min-w-0 text-right text-cn-fg', column.numeric && 'font-cn-mono tabular-nums')}>{column.render(row)}</dd>
                          </div>
                        ),
                      )}
                  </dl>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {/* One live region for both layouts; present before loading starts so the change is announced. */}
      <span role="status" className="sr-only">
        {loading ? `Loading ${caption.toLowerCase()}` : ''}
      </span>
    </div>
  );
}
