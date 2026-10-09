'use client';

import { type ReactNode, useId } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

export interface RadioCardOption<T extends string> {
  value: T;
  label: ReactNode;
  description?: ReactNode;
  /** Shown above the label: a sample, a swatch, a mini screen. */
  media?: ReactNode;
  /** Shown at the end of the label row: a plan badge. */
  badge?: ReactNode;
}

/**
 * RadioGroup in the `cards` layout (DS-L5, local until promoted). Native radios
 * in a fieldset, so arrows move and select and the group is one Tab stop.
 * The picked card gets the 2 px amber edge (07 §2.3); the radio dot says it too,
 * so the choice never rests on colour alone.
 */
export function RadioCards<T extends string>({
  legend,
  hideLegend = false,
  options,
  value,
  onValueChange,
  className,
  cardClassName,
}: {
  legend: ReactNode;
  hideLegend?: boolean;
  options: ReadonlyArray<RadioCardOption<T>>;
  value: T;
  onValueChange: (value: T) => void;
  /** Grid classes for the cards, e.g. `grid-cols-3`. */
  className?: string;
  cardClassName?: string;
}) {
  const name = useId();
  return (
    <fieldset className="min-w-0 space-y-2">
      <legend className={cx('mb-2 text-cn-label font-semibold text-cn-fg', hideLegend && 'sr-only')}>{legend}</legend>
      <div className={cx('grid gap-2', className)}>
        {options.map((option) => {
          const checked = option.value === value;
          return (
            <label
              key={option.value}
              className={cx(
                'relative flex min-w-0 cursor-pointer flex-col gap-2 rounded-cn-lg border p-3 transition-colors duration-cn-fast ease-cn-standard',
                checked ? 'border-cn-accent-border bg-cn-surface-active' : 'border-cn-border bg-cn-surface-sunken hover:bg-cn-surface-hover',
                cardClassName,
              )}
            >
              {option.media}
              <span className="flex min-w-0 items-start gap-2">
                <input
                  type="radio"
                  name={name}
                  value={option.value}
                  checked={checked}
                  onChange={() => onValueChange(option.value)}
                  className={cx(
                    'peer mt-0.5 size-4 shrink-0 appearance-none rounded-cn-full border border-cn-control-border bg-cn-field',
                    'checked:border-4 checked:border-cn-accent',
                    focusRing,
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex min-w-0 items-center justify-between gap-2">
                    <span className="truncate text-cn-label font-semibold text-cn-fg">{option.label}</span>
                    {option.badge}
                  </span>
                  {option.description && (
                    <span className={cx('mt-0.5 block text-cn-caption', checked ? 'text-cn-fg-secondary' : 'text-cn-fg-muted')}>{option.description}</span>
                  )}
                </span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
