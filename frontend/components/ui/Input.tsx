import type { ComponentPropsWithRef, ReactNode } from 'react';

import { type ControlSize, controlHeight, cx, fieldEdge, focusWithinRing } from '@/lib/design/styles';

import { Field } from './Field';

const TEXT: Record<ControlSize, string> = {
  sm: 'text-cn-label px-2.5 gap-2 rounded-cn-sm',
  md: 'text-cn-body px-3 gap-2 rounded-cn-md',
  // 16px stops iOS zooming into the field on focus.
  lg: 'text-cn-body-lg px-3.5 gap-2.5 rounded-cn-md',
};

export interface InputProps extends Omit<ComponentPropsWithRef<'input'>, 'size'> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  size?: ControlSize;
  /** Icon or text before the value (search icon, "https://"). Decorative. */
  leading?: ReactNode;
  /** Icon, unit or IconButton after the value. */
  trailing?: ReactNode;
  /** Classes for the outer field wrapper (width, margin). */
  className?: string;
}

export function Input({
  label,
  hint,
  error,
  size = 'md',
  leading,
  trailing,
  className,
  id,
  required,
  disabled,
  ...rest
}: InputProps) {
  return (
    <Field label={label} hint={hint} error={error} required={required} id={id} className={className}>
      {({ inputId, describedBy }) => (
        <div
          className={cx(
            'flex items-center border transition-colors duration-cn-fast',
            controlHeight[size],
            TEXT[size],
            fieldEdge({ invalid: Boolean(error), disabled }),
            focusWithinRing,
          )}
        >
          {leading && (
            <span aria-hidden className="inline-flex shrink-0 text-cn-fg-muted [&_svg]:size-4">
              {leading}
            </span>
          )}
          <input
            id={inputId}
            required={required}
            disabled={disabled}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className="h-full min-w-0 flex-1 bg-transparent text-cn-fg placeholder:text-cn-fg-muted focus-visible:outline-none disabled:cursor-not-allowed"
            {...rest}
          />
          {trailing && <span className="inline-flex shrink-0 items-center text-cn-fg-muted [&_svg]:size-4">{trailing}</span>}
        </div>
      )}
    </Field>
  );
}
