'use client';

import { type ChangeEvent, type ComponentPropsWithRef, type ReactNode, useRef, useState } from 'react';

import { mergeRefs } from '@/lib/design/refs';
import { cx, fieldEdge, focusRing } from '@/lib/design/styles';
import { useAutosize } from '@/lib/design/useAutosize';

import { Field } from './Field';

export interface TextareaProps extends Omit<ComponentPropsWithRef<'textarea'>, 'rows'> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  /** Visible rows when empty. Default 3. */
  minRows?: number;
  /** Grows with its content up to this many rows, then scrolls. Default 8. */
  maxRows?: number;
  /** Shows "12 / 500" under the field when `maxLength` is set. Default true. */
  showCount?: boolean;
  className?: string;
}

export function Textarea({
  label,
  hint,
  error,
  minRows = 3,
  maxRows = 8,
  showCount = true,
  className,
  id,
  required,
  disabled,
  value,
  defaultValue,
  onChange,
  maxLength,
  ref,
  ...rest
}: TextareaProps) {
  const innerRef = useRef<HTMLTextAreaElement>(null);
  const [uncontrolled, setUncontrolled] = useState(String(defaultValue ?? ''));
  const text = value !== undefined ? String(value) : uncontrolled;
  useAutosize(innerRef, text, minRows, maxRows);

  const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    if (value === undefined) setUncontrolled(event.target.value);
    onChange?.(event);
  };

  return (
    <Field label={label} hint={hint} error={error} required={required} id={id} className={className}>
      {({ inputId, describedBy }) => (
        <div className="flex flex-col gap-1">
          <textarea
            ref={mergeRefs(innerRef, ref)}
            id={inputId}
            rows={minRows}
            required={required}
            disabled={disabled}
            value={value}
            defaultValue={defaultValue}
            onChange={handleChange}
            maxLength={maxLength}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={cx(
              'w-full resize-none rounded-cn-md border px-3 py-2 text-cn-body text-cn-fg placeholder:text-cn-fg-muted',
              'transition-colors duration-cn-fast',
              fieldEdge({ invalid: Boolean(error), disabled }),
              focusRing,
            )}
            {...rest}
          />
          {showCount && maxLength !== undefined && (
            <span className="self-end font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">
              {text.length} / {maxLength}
            </span>
          )}
        </div>
      )}
    </Field>
  );
}
