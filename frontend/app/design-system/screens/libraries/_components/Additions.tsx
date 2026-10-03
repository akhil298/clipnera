'use client';

/**
 * Design-system additions this screen set needs. They are built here, inside
 * the mockup folder, as working briefs; docs/revamp/screens/03 lists each one
 * for the Design System owner to promote into components/ui/.
 */

import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, ArrowDown, ArrowUp, Check, ChevronDown, CircleAlert, CircleCheck, Info, UploadCloud } from 'lucide-react';
import {
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';

import { Checkbox } from '@/components/ui/Checkbox';
import { Portal } from '@/components/ui/Portal';
import { useDismissOnOutsidePointer, useLayer } from '@/lib/design/layers';
import { motionPreset } from '@/lib/design/motion';
import { controlHeight, cx, fieldEdge, floatingSurface, focusRing, focusWithinRing } from '@/lib/design/styles';
import { useAnchoredPosition } from '@/lib/design/useAnchoredPosition';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

/* ------------------------------------------------------------------------ */
/* Avatar (02 §3.23)                                                         */
/* ------------------------------------------------------------------------ */

const AVATAR_SIZE = { 24: 'size-6 text-cn-caption', 32: 'size-8 text-cn-caption', 40: 'size-10 text-cn-label' } as const;

export function Avatar({ name, size = 32, workspace = false, alt }: { name: string; size?: keyof typeof AVATAR_SIZE; workspace?: boolean; alt?: string }) {
  const initials = name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
  return (
    <span
      role={alt ? 'img' : undefined}
      aria-label={alt}
      aria-hidden={alt ? undefined : true}
      className={cx(
        'inline-flex shrink-0 items-center justify-center bg-cn-surface-active font-semibold text-cn-fg-secondary',
        workspace ? 'rounded-cn-sm' : 'rounded-cn-full',
        AVATAR_SIZE[size],
      )}
    >
      {initials}
    </span>
  );
}

/* ------------------------------------------------------------------------ */
/* Callout: an inline message that stays in place (errors that block work,   */
/* pending states, plan notices). Not a toast.                               */
/* ------------------------------------------------------------------------ */

const CALLOUT = {
  info: { box: 'border-cn-info/30 bg-cn-info-subtle', icon: <Info className="text-cn-info-text" /> },
  warning: { box: 'border-cn-accent/30 bg-cn-accent-subtle', icon: <AlertTriangle className="text-cn-accent-text" /> },
  danger: { box: 'border-cn-danger/30 bg-cn-danger-subtle', icon: <CircleAlert className="text-cn-danger-text" /> },
  success: { box: 'border-cn-success/30 bg-cn-success-subtle', icon: <CircleCheck className="text-cn-success-text" /> },
  neutral: { box: 'border-cn-border bg-cn-surface', icon: <Info className="text-cn-fg-muted" /> },
} as const;

export function Callout({
  tone = 'neutral',
  title,
  children,
  action,
  live,
  className,
}: {
  tone?: keyof typeof CALLOUT;
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  /** `alert` for an error that just happened; `status` for a state change. Omit for standing notices. */
  live?: 'alert' | 'status';
  className?: string;
}) {
  return (
    <div role={live} className={cx('flex flex-wrap items-start gap-3 rounded-cn-lg border p-3 sm:flex-nowrap', CALLOUT[tone].box, className)}>
      <span aria-hidden className="mt-0.5 [&_svg]:size-4">
        {CALLOUT[tone].icon}
      </span>
      <div className="min-w-0 flex-1 space-y-0.5 text-cn-body text-cn-fg">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="text-cn-fg-secondary">{children}</div>}
      </div>
      {action && <div className="flex shrink-0 flex-wrap gap-2">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------------ */
/* RadioGroup (02 §3.8)                                                      */
/* ------------------------------------------------------------------------ */

export interface RadioOption<T extends string> {
  value: T;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

/** Native radios in a fieldset; arrows move and select (browser behaviour). */
export function RadioGroup<T extends string>({
  legend,
  hideLegend,
  options,
  value,
  onValueChange,
  error,
  layout = 'stack',
  name,
}: {
  legend: ReactNode;
  hideLegend?: boolean;
  options: ReadonlyArray<RadioOption<T>>;
  value: T | null;
  onValueChange: (value: T) => void;
  error?: ReactNode;
  layout?: 'stack' | 'inline' | 'cards';
  name?: string;
}) {
  const generated = useId();
  const groupName = name ?? generated;
  const errorId = `${groupName}-error`;
  return (
    <fieldset aria-describedby={error ? errorId : undefined} aria-invalid={error ? true : undefined} className="min-w-0 space-y-2">
      <legend className={cx('text-cn-label font-semibold text-cn-fg', hideLegend && 'sr-only')}>{legend}</legend>
      <div className={cx(layout === 'inline' && 'flex flex-wrap gap-x-5 gap-y-2', layout === 'stack' && 'space-y-2', layout === 'cards' && 'grid gap-2 sm:grid-cols-2')}>
        {options.map((option) => {
          const id = `${groupName}-${option.value}`;
          const checked = value === option.value;
          return (
            <label
              key={option.value}
              htmlFor={id}
              className={cx(
                'flex min-h-6 items-start gap-2.5',
                option.disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
                layout === 'cards' && cx('rounded-cn-lg border p-3', checked ? 'border-cn-accent-border bg-cn-accent-subtle' : 'border-cn-border hover:border-cn-border-strong'),
              )}
            >
              <span className="relative mt-0.5 inline-flex size-4 shrink-0">
                <input
                  id={id}
                  type="radio"
                  name={groupName}
                  value={option.value}
                  checked={checked}
                  disabled={option.disabled}
                  onChange={() => onValueChange(option.value)}
                  className={cx(
                    'peer size-4 appearance-none rounded-cn-full border bg-cn-field transition-colors duration-cn-fast',
                    error ? 'border-cn-danger-text' : 'border-cn-control-border hover:border-cn-fg-muted',
                    'checked:border-cn-accent-border',
                    focusRing,
                  )}
                />
                <span aria-hidden className="pointer-events-none absolute inset-1 hidden rounded-cn-full bg-cn-accent peer-checked:block" />
              </span>
              <span className="min-w-0">
                <span className="block text-cn-body text-cn-fg">{option.label}</span>
                {option.description && <span className="block text-cn-label text-cn-fg-muted">{option.description}</span>}
              </span>
            </label>
          );
        })}
      </div>
      {error && (
        <p id={errorId} className="flex items-center gap-1.5 text-cn-label text-cn-danger-text">
          <CircleAlert aria-hidden className="size-3.5" /> {error}
        </p>
      )}
    </fieldset>
  );
}

/* ------------------------------------------------------------------------ */
/* SelectField: the Select rebuild (02 §3.5)                                 */
/* ------------------------------------------------------------------------ */

export interface SelectOption<T extends string> {
  value: T;
  label: string;
  hint?: string;
  disabled?: boolean;
}

/**
 * Button + listbox (APG "select-only combobox"): ↑↓ move, Home/End, type to
 * select, Enter/Space choose, Escape closes. The list is portalled at
 * `z-cn-popover`, so it works inside dialogs and drawers.
 */
export function SelectField<T extends string>({
  label,
  hideLabel,
  options,
  value,
  onValueChange,
  placeholder = 'Choose…',
  hint,
  error,
  disabled,
  size = 'md',
  className,
}: {
  label: string;
  hideLabel?: boolean;
  options: ReadonlyArray<SelectOption<T>>;
  value: T | null;
  onValueChange: (value: T) => void;
  placeholder?: string;
  hint?: ReactNode;
  error?: ReactNode;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}) {
  const id = useId();
  const reduced = useReducedMotion();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const selectedIndex = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const [active, setActive] = useState(selectedIndex);
  const typed = useRef({ text: '', at: 0 });
  const { style, ready } = useAnchoredPosition(open, triggerRef, listRef, { side: 'bottom', align: 'start', offset: 4, matchWidth: true });
  const close = (focus = true) => {
    setOpen(false);
    if (focus) triggerRef.current?.focus();
  };
  useLayer(open, () => close());
  useDismissOnOutsidePointer(open, [triggerRef, listRef], () => close(false));

  useEffect(() => {
    if (open && ready) listRef.current?.focus();
  }, [open, ready]);

  const choose = (index: number) => {
    const option = options[index];
    if (!option || option.disabled) return;
    onValueChange(option.value);
    close();
  };

  const step = (from: number, dir: 1 | -1) => {
    for (let i = from + dir; i >= 0 && i < options.length; i += dir) if (!options[i].disabled) return i;
    return from;
  };

  const onListKey = (event: KeyboardEvent<HTMLUListElement>) => {
    const keys: Record<string, () => number> = {
      ArrowDown: () => step(active, 1),
      ArrowUp: () => step(active, -1),
      Home: () => step(-1, 1),
      End: () => step(options.length, -1),
    };
    if (keys[event.key]) {
      event.preventDefault();
      setActive(keys[event.key]());
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose(active);
    } else if (event.key === 'Tab') {
      close(false);
    } else if (event.key.length === 1) {
      const now = Date.now();
      typed.current = { text: (now - typed.current.at > 500 ? '' : typed.current.text) + event.key.toLowerCase(), at: now };
      const match = options.findIndex((o) => !o.disabled && o.label.toLowerCase().startsWith(typed.current.text));
      if (match >= 0) setActive(match);
    }
  };

  const current = options.find((o) => o.value === value);
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;

  return (
    <div className={cx('flex min-w-0 flex-col gap-1.5', className)}>
      <label id={`${id}-label`} htmlFor={`${id}-trigger`} className={cx('text-cn-label font-semibold text-cn-fg', hideLabel && 'sr-only')}>
        {label}
      </label>
      <button
        ref={triggerRef}
        id={`${id}-trigger`}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${id}-list` : undefined}
        aria-labelledby={`${id}-label ${id}-trigger`}
        aria-invalid={error ? true : undefined}
        aria-describedby={[errorId, hintId].filter(Boolean).join(' ') || undefined}
        disabled={disabled}
        onClick={() => {
          setActive(selectedIndex);
          setOpen((o) => !o);
        }}
        onKeyDown={(event) => {
          if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
            event.preventDefault();
            setActive(selectedIndex);
            setOpen(true);
          }
        }}
        className={cx(
          'flex w-full items-center justify-between gap-2 rounded-cn-md border px-3 text-left transition-colors duration-cn-fast',
          size === 'lg' ? 'text-cn-body-lg' : size === 'sm' ? 'text-cn-label' : 'text-cn-body',
          controlHeight[size],
          fieldEdge({ invalid: !!error, disabled }),
          focusRing,
        )}
      >
        <span className={cx('truncate', current ? 'text-cn-fg' : 'text-cn-fg-muted')}>{current?.label ?? placeholder}</span>
        <ChevronDown aria-hidden className="size-4 shrink-0 text-cn-fg-muted" />
      </button>
      {error && (
        <p id={errorId} className="flex items-center gap-1.5 text-cn-label text-cn-danger-text">
          <CircleAlert aria-hidden className="size-3.5" /> {error}
        </p>
      )}
      {hint && (
        <p id={hintId} className="text-cn-label text-cn-fg-muted">
          {hint}
        </p>
      )}
      <Portal>
        <AnimatePresence>
          {open && (
            <motion.ul
              ref={listRef}
              id={`${id}-list`}
              role="listbox"
              tabIndex={-1}
              aria-labelledby={`${id}-label`}
              aria-activedescendant={`${id}-opt-${active}`}
              onKeyDown={onListKey}
              style={style}
              className={cx(floatingSurface, 'fixed z-cn-popover max-h-72 overflow-y-auto p-1 focus-visible:outline-none', !ready && 'invisible')}
              {...motionPreset('rise', reduced)}
            >
              {options.map((option, index) => {
                const selected = option.value === value;
                return (
                  <li
                    key={option.value}
                    id={`${id}-opt-${index}`}
                    role="option"
                    aria-selected={selected}
                    aria-disabled={option.disabled || undefined}
                    onPointerMove={() => !option.disabled && setActive(index)}
                    onClick={() => choose(index)}
                    className={cx(
                      'flex cursor-pointer items-start gap-2 rounded-cn-sm px-2.5 py-2 text-cn-body',
                      index === active && 'bg-cn-surface-hover ring-1 ring-inset ring-cn-border-strong',
                      option.disabled && 'cursor-not-allowed text-cn-fg-disabled',
                    )}
                  >
                    <Check aria-hidden className={cx('mt-0.5 size-4 shrink-0 text-cn-accent-text', !selected && 'invisible')} />
                    <span className="min-w-0">
                      <span className="block">{option.label}</span>
                      {option.hint && <span className="block text-cn-label text-cn-fg-muted">{option.hint}</span>}
                    </span>
                  </li>
                );
              })}
            </motion.ul>
          )}
        </AnimatePresence>
      </Portal>
    </div>
  );
}

/* ------------------------------------------------------------------------ */
/* DataTable (02 §3.18)                                                      */
/* ------------------------------------------------------------------------ */

export interface Column<R> {
  key: string;
  header: string;
  /** Hidden visually but kept for screen readers (action columns). */
  hideHeader?: boolean;
  numeric?: boolean;
  /** Sort state; the header becomes a button with `aria-sort`. */
  sort?: 'ascending' | 'descending' | 'none';
  className?: string;
  render: (row: R) => ReactNode;
  /** Shown as the card title on phones. */
  primary?: boolean;
}

/**
 * Semantic table on tablet and up; stacked cards on phones (never a sideways
 * scrolling table for primary data). Selection uses Checkbox with an
 * indeterminate select-all.
 */
export function DataTable<R extends { id: string }>({
  caption,
  hideCaption = true,
  columns,
  rows,
  selected,
  onToggle,
  onToggleAll,
  rowHref,
}: {
  caption: string;
  hideCaption?: boolean;
  columns: ReadonlyArray<Column<R>>;
  rows: ReadonlyArray<R>;
  selected?: ReadonlySet<string>;
  onToggle?: (id: string) => void;
  onToggleAll?: () => void;
  /** Marks rows as links (whole-row overlay on the primary cell). */
  rowHref?: boolean;
}) {
  const selectable = !!selected && !!onToggle;
  const all = selectable && rows.length > 0 && rows.every((r) => selected!.has(r.id));
  const some = selectable && !all && rows.some((r) => selected!.has(r.id));
  return (
    <>
      <table className="hidden w-full border-collapse text-left md:table">
        <caption className={cx('text-left text-cn-label text-cn-fg-muted', hideCaption && 'sr-only')}>{caption}</caption>
        <thead>
          <tr className="h-9 border-b border-cn-border">
            {selectable && (
              <th scope="col" className="w-10 px-3">
                <SelectAllBox checked={all} indeterminate={some} onChange={() => onToggleAll?.()} />
              </th>
            )}
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                aria-sort={col.sort}
                className={cx('px-3 text-cn-caption font-medium text-cn-fg-muted', col.numeric && 'text-right', col.className)}
              >
                {col.hideHeader ? <span className="sr-only">{col.header}</span> : col.sort ? (
                  <button type="button" className={cx('inline-flex items-center gap-1 rounded-cn-xs hover:text-cn-fg', focusRing)}>
                    {col.header}
                    {col.sort === 'ascending' && <ArrowUp aria-hidden className="size-3" />}
                    {col.sort === 'descending' && <ArrowDown aria-hidden className="size-3" />}
                  </button>
                ) : (
                  col.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isSelected = selected?.has(row.id);
            return (
              <tr
                key={row.id}
                className={cx(
                  'relative h-11 border-b border-cn-border text-cn-body',
                  isSelected ? 'bg-cn-accent-subtle' : 'hover:bg-cn-surface-hover',
                  rowHref && focusWithinRing,
                )}
              >
                {selectable && (
                  <td className="w-10 px-3">
                    <SelectBox checked={!!isSelected} onChange={() => onToggle!(row.id)} />
                  </td>
                )}
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cx('px-3 py-2 align-middle', col.numeric && 'text-right font-cn-mono tabular-nums', col.className)}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      <ul aria-label={caption} className="space-y-2 md:hidden">
        {rows.map((row) => (
          <li key={row.id} className={cx('relative rounded-cn-lg border p-3', selected?.has(row.id) ? 'border-cn-accent-border bg-cn-accent-subtle' : 'border-cn-border bg-cn-surface')}>
            <dl className="space-y-1.5">
              {columns.map((col) =>
                col.primary ? (
                  <div key={col.key} className="text-cn-body font-semibold">
                    <dt className="sr-only">{col.header}</dt>
                    <dd>{col.render(row)}</dd>
                  </div>
                ) : (
                  <div key={col.key} className="flex items-start justify-between gap-3 text-cn-label">
                    <dt className={cx('text-cn-fg-muted', col.hideHeader && 'sr-only')}>{col.header}</dt>
                    <dd className={cx('min-w-0 text-right text-cn-fg', col.numeric && 'font-cn-mono tabular-nums')}>{col.render(row)}</dd>
                  </div>
                ),
              )}
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}

function SelectBox({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return <Checkbox className="relative z-cn-raised" checked={checked} onChange={onChange} label={<span className="sr-only">Select row</span>} />;
}

function SelectAllBox({ checked, indeterminate, onChange }: { checked: boolean; indeterminate: boolean; onChange: () => void }) {
  return <Checkbox checked={checked} indeterminate={indeterminate} onChange={onChange} label={<span className="sr-only">Select all rows</span>} />;
}

/* ------------------------------------------------------------------------ */
/* Meters and stats                                                          */
/* ------------------------------------------------------------------------ */

/**
 * StorageMeter (05 §3.3): neutral below 80 %, amber from 80 %, rose at 100 %.
 * The fill is never the only signal: the sentence says the same thing.
 */
export function StorageMeter({ used, total, items, breakdown, compact }: { used: number; total: number; items?: number; breakdown?: ReadonlyArray<{ label: string; value: number }>; compact?: boolean }) {
  const ratio = Math.min(used / total, 1);
  const tone = ratio >= 1 ? 'bg-cn-danger' : ratio >= 0.8 ? 'bg-cn-accent' : 'bg-cn-fg-secondary';
  const fmt = (gb: number) => (gb < 1 ? `${Math.round(gb * 1024)} MB` : `${gb.toFixed(gb < 10 ? 1 : 0)} GB`);
  return (
    <div className={cx('min-w-0 space-y-1.5', compact ? 'w-48' : 'w-full')}>
      <div className="flex items-baseline justify-between gap-2 text-cn-label">
        <span className="font-semibold text-cn-fg">Storage</span>
        <span className="font-cn-mono tabular-nums text-cn-fg-secondary">
          {fmt(used)} of {fmt(total)}
          {items !== undefined && !compact && ` · ${items} clips`}
        </span>
      </div>
      <div
        role="meter"
        aria-label="Library storage"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={used}
        aria-valuetext={`${fmt(used)} of ${fmt(total)} used`}
        className="flex h-1.5 overflow-hidden rounded-cn-full bg-cn-surface-active"
      >
        {breakdown
          ? breakdown.map((part, i) => (
              <span key={part.label} className={cx('h-full', i === 0 ? tone : i === 1 ? `${tone} opacity-60` : `${tone} opacity-30`)} style={{ width: `${(part.value / total) * 100}%` }} />
            ))
          : <span className={cx('h-full', tone)} style={{ width: `${ratio * 100}%` }} />}
      </div>
      {breakdown && !compact && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-cn-caption text-cn-fg-muted">
          {breakdown.map((part, i) => (
            <li key={part.label} className="inline-flex items-center gap-1.5">
              <span aria-hidden className={cx('size-2 rounded-cn-full', tone, i === 1 && 'opacity-60', i === 2 && 'opacity-30')} />
              {part.label} <span className="font-cn-mono tabular-nums">{fmt(part.value)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function UsageMeter({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const full = limit !== null && used >= limit;
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-cn-label">
        <span className="text-cn-fg">{label}</span>
        <span className={cx('font-cn-mono tabular-nums', full ? 'text-cn-danger-text' : 'text-cn-fg-secondary')}>
          {limit === null ? `${used} · no limit` : `${used} / ${limit}`}
        </span>
      </div>
      {limit !== null && (
        <div
          role="meter"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-valuenow={used}
          aria-valuetext={full ? `${used} of ${limit}, limit reached` : `${used} of ${limit}`}
          className="h-1 overflow-hidden rounded-cn-full bg-cn-surface-active"
        >
          <span className={cx('block h-full', full ? 'bg-cn-danger' : 'bg-cn-fg-secondary')} style={{ width: `${Math.min(used / limit, 1) * 100}%` }} />
        </div>
      )}
    </div>
  );
}

/** Admin KPI tile (successor to AdminUi's StatTile, on tokens). */
export function StatTile({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: 'accent' }) {
  return (
    <div className={cx('rounded-cn-lg border bg-cn-surface p-4', tone === 'accent' ? 'border-cn-accent-border' : 'border-cn-border')}>
      <p className="text-cn-caption text-cn-fg-muted">{label}</p>
      <p className="mt-1 font-cn-mono text-cn-title font-semibold tabular-nums text-cn-fg">{value}</p>
      {hint && <p className={cx('mt-0.5 text-cn-caption', tone === 'accent' ? 'text-cn-accent-text' : 'text-cn-fg-muted')}>{hint}</p>}
    </div>
  );
}

/** Label → value pairs (licence record, technical details, plan summary). */
export function KeyValues({ items, className }: { items: ReadonlyArray<{ label: string; value: ReactNode }>; className?: string }) {
  return (
    <dl className={cx('divide-y divide-cn-border text-cn-body', className)}>
      {items.map((item) => (
        <div key={item.label} className="flex items-start justify-between gap-4 py-2">
          <dt className="shrink-0 text-cn-fg-muted">{item.label}</dt>
          <dd className="min-w-0 text-right text-cn-fg">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------------ */
/* Drop zone                                                                 */
/* ------------------------------------------------------------------------ */

/** A real file input inside a label: click, keyboard (Enter/Space) and drop all work. */
export function Dropzone({
  title,
  hint,
  accept,
  multiple,
  disabled,
  disabledReason,
  dragging,
  compact,
}: {
  title: string;
  hint: ReactNode;
  accept: string;
  multiple?: boolean;
  disabled?: boolean;
  disabledReason?: string;
  /** Mockup: show the drag-over look. */
  dragging?: boolean;
  compact?: boolean;
}) {
  const id = useId();
  return (
    <label
      htmlFor={id}
      className={cx(
        'flex flex-col items-center justify-center gap-2 rounded-cn-xl border border-dashed text-center transition-colors duration-cn-fast',
        compact ? 'px-4 py-6' : 'px-6 py-12',
        disabled ? 'cursor-not-allowed border-cn-border opacity-60' : 'cursor-pointer',
        !disabled && (dragging ? 'border-cn-accent-border bg-cn-accent-subtle' : 'border-cn-control-border hover:border-cn-fg-muted hover:bg-cn-surface-hover'),
        focusWithinRing,
      )}
    >
      <input id={id} type="file" accept={accept} multiple={multiple} disabled={disabled} className="sr-only" aria-describedby={`${id}-hint`} />
      <span aria-hidden className="inline-flex size-12 items-center justify-center rounded-cn-lg border border-cn-border bg-cn-surface text-cn-fg-secondary">
        <UploadCloud className="size-5" />
      </span>
      <span className="text-cn-body font-semibold text-cn-fg">{dragging ? 'Drop to upload' : title}</span>
      <span id={`${id}-hint`} className="max-w-md text-cn-label text-cn-fg-muted">
        {disabled && disabledReason ? disabledReason : hint}
      </span>
    </label>
  );
}

/* ------------------------------------------------------------------------ */
/* Sticky save bar (brand kit, flag detail, remote config)                   */
/* ------------------------------------------------------------------------ */

export function SaveBar({ children, show }: { children: ReactNode; show: boolean }) {
  const reduced = useReducedMotion();
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          role="region"
          aria-label="Unsaved changes"
          className="sticky bottom-0 z-cn-sticky border-t border-cn-border-strong bg-cn-surface-raised shadow-cn-2"
          {...motionPreset('rise', reduced)}
        >
          <div className="mx-auto flex max-w-screen-xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">{children}</div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------------ */
/* Platform marks: the only place brand colours appear (02 §2.1)             */
/* ------------------------------------------------------------------------ */

const PLATFORM = {
  youtube: { name: 'YouTube', bg: '#ff0000', glyph: <path d="M10 8.5v7l6-3.5z" fill="#fff" /> },
  instagram: {
    name: 'Instagram',
    bg: '#d62976',
    glyph: (
      <>
        <rect x="6.5" y="6.5" width="11" height="11" rx="3.2" fill="none" stroke="#fff" strokeWidth="1.6" />
        <circle cx="12" cy="12" r="2.6" fill="none" stroke="#fff" strokeWidth="1.6" />
        <circle cx="15.3" cy="8.7" r="0.8" fill="#fff" />
      </>
    ),
  },
} as const;

export type PlatformId = keyof typeof PLATFORM;

/** Official marks go here in production (owner question 02 §12 q6). Decorative unless `label` is set. */
export function PlatformMark({ platform, size = 20, label }: { platform: PlatformId; size?: number; label?: boolean }) {
  const p = PLATFORM[platform];
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      role={label ? 'img' : undefined}
      aria-label={label ? p.name : undefined}
      aria-hidden={label ? undefined : true}
      className="shrink-0"
    >
      <rect width="24" height="24" rx="6" fill={p.bg} />
      {p.glyph}
    </svg>
  );
}

export const platformName = (platform: PlatformId) => PLATFORM[platform].name;

/* ------------------------------------------------------------------------ */
/* Rollout slider (06-flags §10.2)                                           */
/* ------------------------------------------------------------------------ */

const STOPS = [0, 1, 10, 50, 100] as const;

/**
 * Native range (arrows ±1 %, Page keys ±10 %, Home/End) plus stop buttons and
 * a numeric field to 0.01 %. Value in basis points to match `rollout_bps`.
 */
export function RolloutSlider({ bps, onChange, activeUsers, disabled }: { bps: number; onChange: (bps: number) => void; activeUsers: number; disabled?: boolean }) {
  const id = useId();
  const pct = bps / 100;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 space-y-2">
          <label htmlFor={`${id}-range`} className="text-cn-label font-semibold text-cn-fg">
            Everyone else
          </label>
          <input
            id={`${id}-range`}
            type="range"
            min={0}
            max={10000}
            step={100}
            value={bps}
            disabled={disabled}
            aria-valuetext={`${pct}% of users`}
            onChange={(e) => onChange(Number(e.target.value))}
            className={cx('block h-6 w-full cursor-pointer accent-cn-accent disabled:cursor-not-allowed disabled:opacity-50', focusRing)}
          />
        </div>
        <div className="w-28">
          <label htmlFor={`${id}-num`} className="sr-only">
            Rollout percentage
          </label>
          <div className={cx('flex h-9 items-center rounded-cn-md border px-2.5', fieldEdge({ disabled }), focusWithinRing)}>
            <input
              id={`${id}-num`}
              type="number"
              min={0}
              max={100}
              step={0.01}
              value={pct}
              disabled={disabled}
              onChange={(e) => onChange(Math.round(Number(e.target.value) * 100))}
              className="w-full bg-transparent font-cn-mono text-cn-body tabular-nums text-cn-fg focus-visible:outline-none"
            />
            <span className="text-cn-label text-cn-fg-muted">%</span>
          </div>
        </div>
      </div>
      <div role="group" aria-label="Quick stops" className="flex flex-wrap gap-1.5">
        {STOPS.map((stop) => (
          <button
            key={stop}
            type="button"
            disabled={disabled}
            aria-pressed={pct === stop}
            onClick={() => onChange(stop * 100)}
            className={cx(
              'h-7 rounded-cn-full border px-2.5 font-cn-mono text-cn-caption tabular-nums',
              pct === stop ? 'border-cn-accent-border bg-cn-accent-subtle text-cn-accent-text' : 'border-cn-border text-cn-fg-secondary hover:bg-cn-surface-hover',
              'disabled:opacity-50',
              focusRing,
            )}
          >
            {stop}%
          </button>
        ))}
      </div>
      <p className="text-cn-label text-cn-fg-muted">
        About <span className="font-cn-mono tabular-nums text-cn-fg">{Math.round((activeUsers * bps) / 10000).toLocaleString('en-IN')}</span> of{' '}
        <span className="font-cn-mono tabular-nums">{activeUsers.toLocaleString('en-IN')}</span> active users. Raising it only adds people; nobody who has it loses it.
      </p>
    </div>
  );
}
