'use client';

import { type KeyboardEvent, type ReactNode, useRef } from 'react';

import { cx, focusRing, type ControlSize } from '@/lib/design/styles';
import { useControllableState } from '@/lib/design/useControllableState';

export interface SegmentOption<T extends string> {
  value: T;
  label: ReactNode;
  /** Accessible name when `label` is an icon. */
  ariaLabel?: string;
  disabled?: boolean;
}

export interface SegmentedControlProps<T extends string> {
  /** Accessible name of the group, e.g. "Prompt mode". */
  label: string;
  options: ReadonlyArray<SegmentOption<T>>;
  value?: T;
  defaultValue?: T;
  onValueChange?: (value: T) => void;
  size?: Exclude<ControlSize, 'lg'>;
  className?: string;
}

const SIZE = { sm: 'h-7 px-2.5 text-cn-caption', md: 'h-8 px-3 text-cn-label' } as const;

/**
 * One choice from two to five, always visible: prompt mode (Edit / Ask / Plan),
 * theme, view switch. A radio group: Tab enters at the selected option, arrows move and select.
 */
export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  defaultValue,
  onValueChange,
  size = 'md',
  className,
}: SegmentedControlProps<T>) {
  const [current, setCurrent] = useControllableState<T>(value, defaultValue ?? options[0].value, onValueChange);
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const enabled = options.filter((option) => !option.disabled);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const keys: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (!(event.key in keys) || enabled.length === 0) return;
    event.preventDefault();
    const from = enabled.findIndex((option) => option.value === current);
    const next = enabled[(from + keys[event.key] + enabled.length) % enabled.length];
    setCurrent(next.value);
    refs.current[options.indexOf(next)]?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cx('inline-flex items-center gap-0.5 rounded-cn-md border border-cn-border bg-cn-surface p-0.5', className)}
    >
      {options.map((option, index) => {
        const selected = option.value === current;
        return (
          <button
            key={option.value}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={option.ariaLabel}
            tabIndex={selected ? 0 : -1}
            disabled={option.disabled}
            onClick={() => setCurrent(option.value)}
            className={cx(
              'inline-flex items-center gap-1.5 rounded-cn-sm font-semibold transition-colors duration-cn-fast [&_svg]:size-3.5',
              'disabled:cursor-not-allowed disabled:opacity-50',
              SIZE[size],
              selected
                ? 'bg-cn-surface-active text-cn-fg shadow-cn-1'
                : 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg',
              focusRing,
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
