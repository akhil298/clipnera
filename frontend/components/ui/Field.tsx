import { CircleAlert } from 'lucide-react';
import { type ReactNode, useId } from 'react';

import { cx } from '@/lib/design/styles';

export interface FieldIds {
  inputId: string;
  hintId?: string;
  errorId?: string;
  /** Pass to the control's `aria-describedby`. */
  describedBy?: string;
}

export interface FieldProps {
  /** Visible label. Omit only when the control has an `aria-label`. */
  label?: ReactNode;
  /** Help text under the control; stays visible while an error shows. */
  hint?: ReactNode;
  /** Error text. Sets `aria-invalid` and is announced with the field. */
  error?: ReactNode;
  required?: boolean;
  /** Override the generated id (e.g. to point an external `<label>` at it). */
  id?: string;
  className?: string;
  children: (ids: FieldIds) => ReactNode;
}

/** Label, help text and error message wired to one control. Used by Input, Textarea and future Select. */
export function Field({ label, hint, error, required, id, className, children }: FieldProps) {
  const generated = useId();
  const inputId = id ?? generated;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      {label && (
        <label htmlFor={inputId} className="text-cn-label font-semibold text-cn-fg">
          {label}
          {required && (
            <span className="ml-0.5 text-cn-fg-muted" aria-hidden>
              *
            </span>
          )}
        </label>
      )}
      {children({ inputId, hintId, errorId, describedBy })}
      {error && (
        <p id={errorId} className="flex items-start gap-1.5 text-cn-caption font-medium text-cn-danger-text">
          <CircleAlert aria-hidden className="mt-px size-3.5 shrink-0" />
          {error}
        </p>
      )}
      {hint && (
        <p id={hintId} className="text-cn-caption text-cn-fg-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
