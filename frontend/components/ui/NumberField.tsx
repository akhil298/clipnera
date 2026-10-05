'use client';

import { Minus, Plus } from 'lucide-react';
import { type KeyboardEvent, type ReactNode, useEffect, useState } from 'react';

import { type ControlSize, controlHeight, cx, fieldEdge, focusWithinRing } from '@/lib/design/styles';
import { useControllableState } from '@/lib/design/useControllableState';

import { Field } from './Field';
import { IconButton } from './IconButton';

export interface NumberFieldProps {
  label?: ReactNode;
  /** Accessible name when there is no visible label. */
  ariaLabel?: string;
  hint?: ReactNode;
  error?: ReactNode;
  value?: number | null;
  defaultValue?: number | null;
  onValueChange?: (value: number | null) => void;
  min?: number;
  max?: number;
  /** Arrow keys and the buttons move by this; Shift or Page keys by ten steps. Default 1. */
  step?: number;
  /** Unit after the value: "s", "%", "px". */
  unit?: string;
  /** Allow an empty field (`null`). Default false: an empty field restores the last value on blur. */
  allowEmpty?: boolean;
  size?: ControlSize;
  disabled?: boolean;
  required?: boolean;
  id?: string;
  className?: string;
}

const decimalsOf = (step: number) => (String(step).split('.')[1] ?? '').length;

/**
 * A number with − and + buttons: clip length, font size, rollout percent. The
 * input keeps what is typed while editing and clamps to min/max on blur.
 * ↑↓ step, Shift+↑↓ and Page keys step by ten, Home/End go to min/max.
 */
export function NumberField({
  label,
  ariaLabel,
  hint,
  error,
  value,
  defaultValue = null,
  onValueChange,
  min = Number.NEGATIVE_INFINITY,
  max = Number.POSITIVE_INFINITY,
  step = 1,
  unit,
  allowEmpty = false,
  size = 'md',
  disabled = false,
  required,
  id,
  className,
}: NumberFieldProps) {
  const [current, setCurrent] = useControllableState<number | null>(value, defaultValue, onValueChange);
  const [draft, setDraft] = useState(current === null ? '' : String(current));
  const decimals = decimalsOf(step);

  useEffect(() => setDraft(current === null ? '' : String(current)), [current]);

  const clamp = (n: number) => Number(Math.min(max, Math.max(min, n)).toFixed(decimals));
  const commit = (n: number | null) => {
    const next = n === null ? null : clamp(n);
    setCurrent(next);
    setDraft(next === null ? '' : String(next));
  };
  const nudge = (by: number) => commit((current ?? (Number.isFinite(min) ? min : 0)) + by);

  const onBlur = () => {
    const parsed = draft.trim() === '' ? null : Number(draft.replace(',', '.'));
    if (parsed === null) commit(allowEmpty ? null : current);
    else commit(Number.isNaN(parsed) ? current : parsed);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const big = step * 10;
    const moves: Record<string, () => void> = {
      ArrowUp: () => nudge(event.shiftKey ? big : step),
      ArrowDown: () => nudge(event.shiftKey ? -big : -step),
      PageUp: () => nudge(big),
      PageDown: () => nudge(-big),
      Home: () => Number.isFinite(min) && commit(min),
      End: () => Number.isFinite(max) && commit(max),
      Enter: onBlur,
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    move();
  };

  const atMin = current !== null && current <= min;
  const atMax = current !== null && current >= max;
  const buttonSize = size === 'lg' ? 'md' : 'sm';

  return (
    <Field label={label} hint={hint} error={error} required={required} id={id} className={className}>
      {({ inputId, describedBy }) => (
        <div
          className={cx(
            'flex items-center gap-0.5 rounded-cn-md border px-0.5 transition-colors duration-cn-fast',
            controlHeight[size],
            fieldEdge({ invalid: Boolean(error), disabled }),
            focusWithinRing,
          )}
        >
          <IconButton label="Decrease" icon={<Minus />} size={buttonSize} tooltip={false} tabIndex={-1} disabled={disabled || atMin} onClick={() => nudge(-step)} />
          <input
            id={inputId}
            type="text"
            inputMode={decimals > 0 ? 'decimal' : 'numeric'}
            role="spinbutton"
            aria-label={label ? undefined : ariaLabel}
            aria-valuenow={current ?? undefined}
            aria-valuemin={Number.isFinite(min) ? min : undefined}
            aria-valuemax={Number.isFinite(max) ? max : undefined}
            aria-valuetext={current === null ? 'Empty' : unit ? `${current} ${unit}` : undefined}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            required={required}
            disabled={disabled}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={onBlur}
            onKeyDown={onKeyDown}
            className="h-full min-w-0 flex-1 bg-transparent text-center font-cn-mono text-cn-body tabular-nums text-cn-fg focus-visible:outline-none disabled:cursor-not-allowed"
          />
          {unit && <span aria-hidden className="text-cn-label text-cn-fg-muted">{unit}</span>}
          <IconButton label="Increase" icon={<Plus />} size={buttonSize} tooltip={false} tabIndex={-1} disabled={disabled || atMax} onClick={() => nudge(step)} />
        </div>
      )}
    </Field>
  );
}
