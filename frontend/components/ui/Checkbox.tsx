'use client';

import { Check, Minus } from 'lucide-react';
import { type ComponentPropsWithRef, type ReactNode, useEffect, useId, useRef } from 'react';

import { mergeRefs } from '@/lib/design/refs';
import { cx, focusRing } from '@/lib/design/styles';

export interface CheckboxProps extends Omit<ComponentPropsWithRef<'input'>, 'type' | 'size'> {
  label: ReactNode;
  description?: ReactNode;
  /** "Some selected" in a select-all header. Reads as "mixed". */
  indeterminate?: boolean;
  error?: ReactNode;
}

/**
 * A native checkbox, restyled. Native keeps forms, Space-to-toggle and
 * screen-reader behaviour for free; the label row is the 24px+ hit target.
 */
export function Checkbox({ label, description, indeterminate = false, error, className, id, disabled, ref, ...rest }: CheckboxProps) {
  const generated = useId();
  const inputId = id ?? generated;
  const innerRef = useRef<HTMLInputElement>(null);
  const descriptionId = description ? `${inputId}-description` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;

  useEffect(() => {
    if (innerRef.current) innerRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <div className={cx('flex flex-col gap-1', className)}>
      <label
        htmlFor={inputId}
        className={cx('group inline-flex min-h-6 items-start gap-2.5', disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer')}
      >
        <span className="relative mt-0.5 inline-flex size-4 shrink-0">
          <input
            ref={mergeRefs(innerRef, ref)}
            id={inputId}
            type="checkbox"
            disabled={disabled}
            aria-invalid={error ? true : undefined}
            aria-describedby={[errorId, descriptionId].filter(Boolean).join(' ') || undefined}
            className={cx(
              'peer size-4 cursor-[inherit] appearance-none rounded-cn-xs border bg-cn-field transition-colors duration-cn-fast',
              error ? 'border-cn-danger-text' : 'border-cn-control-border group-hover:border-cn-fg-muted',
              'checked:border-cn-accent-border checked:bg-cn-accent indeterminate:border-cn-accent-border indeterminate:bg-cn-accent',
              focusRing,
            )}
            {...rest}
          />
          <Check
            aria-hidden
            strokeWidth={3}
            className="pointer-events-none absolute inset-0.5 hidden size-3 text-cn-accent-fg peer-checked:block peer-indeterminate:hidden"
          />
          <Minus
            aria-hidden
            strokeWidth={3}
            className="pointer-events-none absolute inset-0.5 hidden size-3 text-cn-accent-fg peer-indeterminate:block"
          />
        </span>
        <span className="flex flex-col gap-0.5">
          <span className="text-cn-body text-cn-fg">{label}</span>
          {description && (
            <span id={descriptionId} className="text-cn-caption text-cn-fg-muted">
              {description}
            </span>
          )}
        </span>
      </label>
      {error && (
        <p id={errorId} className="pl-[26px] text-cn-caption font-medium text-cn-danger-text">
          {error}
        </p>
      )}
    </div>
  );
}
