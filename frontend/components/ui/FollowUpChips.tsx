import { ArrowRight } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { Chip } from './Chip';
import { Skeleton } from './Skeleton';

export interface FollowUp {
  id: string;
  /** The prompt it fills: "Make the hook shorter". */
  label: string;
  icon?: ReactNode;
}

export interface FollowUpChipsProps {
  items: ReadonlyArray<FollowUp | string>;
  /** Fills the prompt bar; never sends on its own (02 §4.6). */
  onPick: (prompt: string) => void;
  /** `chips` under a result; `list` for Perplexity-style "Related" rows. */
  variant?: 'chips' | 'list';
  label?: string;
  /** Visible heading above a `list`. */
  showLabel?: boolean;
  /** Most shown. Default 3 (chips) or 5 (list). */
  max?: number;
  /** Suggestions are still being written. */
  loading?: boolean;
  className?: string;
}

const normalise = (item: FollowUp | string): FollowUp => (typeof item === 'string' ? { id: item, label: item } : item);

/** Next-step prompts after an answer or result. A click fills the prompt bar so the person can edit before sending. */
export function FollowUpChips({
  items,
  onPick,
  variant = 'chips',
  label = 'Suggested next steps',
  showLabel = false,
  max,
  loading = false,
  className,
}: FollowUpChipsProps) {
  const list = variant === 'list';
  const shown = items.slice(0, max ?? (list ? 5 : 3)).map(normalise);

  if (loading) {
    return (
      <div aria-hidden className={cx('flex gap-1.5', list && 'flex-col', className)}>
        {[0, 1, 2].map((index) => (
          <Skeleton key={index} className={list ? 'h-9 w-full' : 'h-7 w-32 rounded-cn-full'} />
        ))}
      </div>
    );
  }
  if (shown.length === 0) return null;

  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      {list && showLabel && <p className="text-cn-caption font-semibold text-cn-fg-muted">{label}</p>}
      <ul aria-label={label} className={list ? 'flex flex-col divide-y divide-cn-border border-y border-cn-border' : 'flex flex-wrap gap-1.5'}>
        {shown.map((item) => (
          <li key={item.id}>
            {list ? (
              <button
                type="button"
                onClick={() => onPick(item.label)}
                className={cx(
                  'flex min-h-10 w-full items-center gap-3 rounded-cn-sm px-1 py-2 text-left text-cn-body text-cn-fg-secondary transition-colors duration-cn-fast',
                  'hover:text-cn-fg active:bg-cn-surface-hover [&_svg]:size-4',
                  focusRing,
                )}
              >
                {item.icon && (
                  <span aria-hidden className="inline-flex shrink-0 text-cn-fg-muted">
                    {item.icon}
                  </span>
                )}
                <span className="min-w-0 flex-1">{item.label}</span>
                <ArrowRight aria-hidden className="shrink-0 text-cn-fg-muted" />
              </button>
            ) : (
              <Chip size="sm" icon={item.icon} onClick={() => onPick(item.label)}>
                {item.label}
              </Chip>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
