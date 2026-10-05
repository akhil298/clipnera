'use client';

import { type ReactNode, useId } from 'react';

import { cx, focusRing } from '@/lib/design/styles';
import { useControllableState } from '@/lib/design/useControllableState';

export interface SwitchProps {
  /** Visible label. Clicking it toggles the switch. */
  label: ReactNode;
  description?: ReactNode;
  checked?: boolean;
  defaultChecked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  /** Put the label after the switch instead of before it (settings rows put it before). */
  labelPosition?: 'start' | 'end';
  /** Hide the label visually but keep it as the accessible name (dense toolbars). */
  hideLabel?: boolean;
  className?: string;
  id?: string;
}

/**
 * An on/off setting that applies immediately. For a choice that is submitted
 * with a form, use Checkbox. Space and Enter toggle it.
 */
export function Switch({
  label,
  description,
  checked,
  defaultChecked = false,
  onCheckedChange,
  disabled = false,
  labelPosition = 'start',
  hideLabel = false,
  className,
  id,
}: SwitchProps) {
  const generated = useId();
  const switchId = id ?? generated;
  const labelId = `${switchId}-label`;
  const descriptionId = description ? `${switchId}-description` : undefined;
  const [on, setOn] = useControllableState(checked, defaultChecked, onCheckedChange);

  const text = (
    <span className={cx('flex min-w-0 flex-1 flex-col gap-0.5', hideLabel && 'sr-only')}>
      <label id={labelId} htmlFor={switchId} className={cx('text-cn-body text-cn-fg', !disabled && 'cursor-pointer')}>
        {label}
      </label>
      {description && (
        <span id={descriptionId} className="text-cn-caption text-cn-fg-muted">
          {description}
        </span>
      )}
    </span>
  );

  return (
    <div className={cx('flex min-h-6 items-center gap-3', disabled && 'opacity-50', className)}>
      {labelPosition === 'start' && text}
      <button
        id={switchId}
        type="button"
        role="switch"
        aria-checked={on}
        aria-labelledby={labelId}
        aria-describedby={descriptionId}
        disabled={disabled}
        onClick={() => setOn(!on)}
        className={cx(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-cn-full border transition-colors duration-cn-fast ease-cn-out',
          'disabled:cursor-not-allowed',
          on ? 'border-cn-accent-border bg-cn-accent' : 'border-cn-control-border bg-cn-surface-active',
          focusRing,
        )}
      >
        <span
          aria-hidden
          className={cx(
            'absolute size-3.5 rounded-cn-full shadow-cn-1 motion-safe:transition-transform motion-safe:duration-cn-fast motion-safe:ease-cn-out',
            on ? 'translate-x-[18px] bg-cn-accent-fg' : 'translate-x-[2px] bg-cn-fg-secondary',
          )}
        />
      </button>
      {labelPosition === 'end' && text}
    </div>
  );
}
