'use client';

import { type KeyboardEvent, type PointerEvent, type ReactNode, useId, useRef } from 'react';

import { cx } from '@/lib/design/styles';
import { useControllableState } from '@/lib/design/useControllableState';

interface ScaleProps {
  min?: number;
  max?: number;
  /** Arrow keys move by this; Shift+arrows and Page keys by ten steps. Default 1. */
  step?: number;
  /** Spoken and shown value: `(v) => \`${v}%\``. Default: the number. */
  formatValue?: (value: number) => string;
  /** Visible label. Also the accessible name. */
  label: ReactNode;
  /** Hide the label row visually (it stays the accessible name). */
  hideLabel?: boolean;
  /** Show the current value at the end of the label row. Default true. */
  showValue?: boolean;
  hint?: ReactNode;
  disabled?: boolean;
  className?: string;
}

const percentOf = (value: number, min: number, max: number) => (max === min ? 0 : ((value - min) / (max - min)) * 100);

function snap(raw: number, min: number, max: number, step: number): number {
  const stepped = Math.round((raw - min) / step) * step + min;
  const decimals = (String(step).split('.')[1] ?? '').length;
  return Number(Math.min(max, Math.max(min, stepped)).toFixed(decimals));
}

/** Keyboard step for a slider thumb, per the WAI-ARIA slider pattern; `null` for keys it ignores. */
function keyStep(event: KeyboardEvent, value: number, min: number, max: number, step: number): number | null {
  const big = step * 10;
  const delta: Record<string, number> = {
    ArrowRight: event.shiftKey ? big : step,
    ArrowUp: event.shiftKey ? big : step,
    ArrowLeft: event.shiftKey ? -big : -step,
    ArrowDown: event.shiftKey ? -big : -step,
    PageUp: big,
    PageDown: -big,
  };
  if (event.key === 'Home') return min;
  if (event.key === 'End') return max;
  return event.key in delta ? snap(value + delta[event.key], min, max, step) : null;
}

function Thumb({
  value,
  percent,
  min,
  max,
  name,
  labelledBy,
  valueText,
  disabled,
  onKey,
  thumbRef,
}: {
  value: number;
  /** Position on the track, 0–100. */
  percent: number;
  min: number;
  max: number;
  name?: string;
  labelledBy: string;
  valueText: string;
  disabled: boolean;
  onKey: (event: KeyboardEvent<HTMLSpanElement>) => void;
  thumbRef?: (node: HTMLSpanElement | null) => void;
}) {
  return (
    <span
      ref={thumbRef}
      role="slider"
      tabIndex={disabled ? -1 : 0}
      aria-label={name}
      aria-labelledby={name ? undefined : labelledBy}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-valuetext={valueText}
      aria-disabled={disabled || undefined}
      onKeyDown={onKey}
      style={{ left: `${percent}%` }}
      className={cx(
        'absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-cn-full border-2 border-cn-accent bg-cn-fg shadow-cn-1',
        'transition-transform duration-cn-fast ease-cn-out motion-safe:hover:scale-110 motion-safe:active:scale-95',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cn-focus',
        disabled ? 'cursor-not-allowed' : 'cursor-grab active:cursor-grabbing',
      )}
    />
  );
}

/** Shared frame: label row, the 24px-tall hit area and its track. */
function SliderFrame({
  label,
  hideLabel,
  showValue,
  valueText,
  hint,
  disabled,
  className,
  labelId,
  fill,
  onPointer,
  children,
}: Pick<ScaleProps, 'label' | 'hideLabel' | 'showValue' | 'hint' | 'disabled' | 'className'> & {
  valueText: string;
  labelId: string;
  fill: { from: number; to: number };
  onPointer: (event: PointerEvent<HTMLDivElement>) => void;
  children: ReactNode;
}) {
  return (
    <div className={cx('flex flex-col gap-1.5', disabled && 'opacity-50', className)}>
      <div className={cx('flex items-baseline justify-between gap-3 text-cn-label', hideLabel && 'sr-only')}>
        <span id={labelId} className="font-semibold text-cn-fg">
          {label}
        </span>
        {showValue && (
          <span aria-hidden className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary">
            {valueText}
          </span>
        )}
      </div>
      <div
        onPointerDown={disabled ? undefined : onPointer}
        className={cx('relative h-6 touch-none select-none', disabled ? 'cursor-not-allowed' : 'cursor-pointer')}
      >
        <span aria-hidden className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-cn-full bg-cn-surface-active" />
        <span
          aria-hidden
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-cn-full bg-cn-accent"
          style={{ left: `${fill.from}%`, width: `${fill.to - fill.from}%` }}
        />
        {children}
      </div>
      {hint && <p className="text-cn-caption text-cn-fg-muted">{hint}</p>}
    </div>
  );
}

/** Pointer position on the track as a value; follows the pointer until release. */
function trackValue(event: PointerEvent<HTMLDivElement> | globalThis.PointerEvent, track: HTMLElement, min: number, max: number, step: number) {
  const rect = track.getBoundingClientRect();
  const ratio = rect.width === 0 ? 0 : (event.clientX - rect.left) / rect.width;
  return snap(min + ratio * (max - min), min, max, step);
}

function dragOnTrack(event: PointerEvent<HTMLDivElement>, onValue: (value: number) => void, toValue: (e: globalThis.PointerEvent) => number) {
  event.preventDefault();
  const move = (e: globalThis.PointerEvent) => onValue(toValue(e));
  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    window.removeEventListener('pointercancel', up);
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
  window.addEventListener('pointercancel', up);
}

export interface SliderProps extends ScaleProps {
  value?: number;
  defaultValue?: number;
  onValueChange?: (value: number) => void;
}

/** One value on a range: volume, caption size, music level. `role="slider"`; click or drag the track, or use the keys. */
export function Slider({
  value,
  defaultValue,
  onValueChange,
  min = 0,
  max = 100,
  step = 1,
  formatValue = String,
  label,
  hideLabel = false,
  showValue = true,
  hint,
  disabled = false,
  className,
}: SliderProps) {
  const labelId = useId();
  const thumbRef = useRef<HTMLSpanElement | null>(null);
  const [current, setCurrent] = useControllableState(value, defaultValue ?? min, onValueChange);
  const set = (next: number) => next !== current && setCurrent(next);

  const onPointer = (event: PointerEvent<HTMLDivElement>) => {
    const track = event.currentTarget;
    set(trackValue(event, track, min, max, step));
    thumbRef.current?.focus();
    dragOnTrack(event, set, (e) => trackValue(e, track, min, max, step));
  };

  const onKey = (event: KeyboardEvent<HTMLSpanElement>) => {
    if (disabled) return;
    const next = keyStep(event, current, min, max, step);
    if (next === null) return;
    event.preventDefault();
    set(next);
  };

  return (
    <SliderFrame
      label={label}
      hideLabel={hideLabel}
      showValue={showValue}
      valueText={formatValue(current)}
      hint={hint}
      disabled={disabled}
      className={className}
      labelId={labelId}
      fill={{ from: 0, to: percentOf(current, min, max) }}
      onPointer={onPointer}
    >
      <Thumb
        thumbRef={(node) => {
          thumbRef.current = node;
        }}
        value={current}
        percent={percentOf(current, min, max)}
        min={min}
        max={max}
        labelledBy={labelId}
        valueText={formatValue(current)}
        disabled={disabled}
        onKey={onKey}
      />
    </SliderFrame>
  );
}

export interface RangeSliderProps extends ScaleProps {
  value?: readonly [number, number];
  defaultValue?: readonly [number, number];
  onValueChange?: (value: readonly [number, number]) => void;
  /** Smallest gap between the two thumbs. Default one step. */
  minGap?: number;
  /** Names for the two thumbs. Default "Minimum" and "Maximum". */
  thumbLabels?: readonly [string, string];
}

/** Two values on one range: a duration filter (15–60 s), a trim window. Thumbs never cross. */
export function RangeSlider({
  value,
  defaultValue,
  onValueChange,
  min = 0,
  max = 100,
  step = 1,
  minGap = step,
  thumbLabels = ['Minimum', 'Maximum'],
  formatValue = String,
  label,
  hideLabel = false,
  showValue = true,
  hint,
  disabled = false,
  className,
}: RangeSliderProps) {
  const labelId = useId();
  const thumbs = useRef<Array<HTMLSpanElement | null>>([]);
  const [range, setRange] = useControllableState<readonly [number, number]>(value, defaultValue ?? [min, max], onValueChange);
  const [low, high] = range;

  const setThumb = (index: 0 | 1, next: number) => {
    const updated: readonly [number, number] = index === 0 ? [Math.min(next, high - minGap), high] : [low, Math.max(next, low + minGap)];
    if (updated[0] !== low || updated[1] !== high) setRange(updated);
  };

  const onPointer = (event: PointerEvent<HTMLDivElement>) => {
    const track = event.currentTarget;
    const at = trackValue(event, track, min, max, step);
    const index: 0 | 1 = Math.abs(at - low) <= Math.abs(at - high) ? 0 : 1;
    setThumb(index, at);
    thumbs.current[index]?.focus();
    dragOnTrack(event, (next) => setThumb(index, next), (e) => trackValue(e, track, min, max, step));
  };

  const onKey = (index: 0 | 1) => (event: KeyboardEvent<HTMLSpanElement>) => {
    if (disabled) return;
    const next = keyStep(event, range[index], min, max, step);
    if (next === null) return;
    event.preventDefault();
    setThumb(index, next);
  };

  const text = `${formatValue(low)} – ${formatValue(high)}`;

  return (
    <SliderFrame
      label={label}
      hideLabel={hideLabel}
      showValue={showValue}
      valueText={text}
      hint={hint}
      disabled={disabled}
      className={className}
      labelId={labelId}
      fill={{ from: percentOf(low, min, max), to: percentOf(high, min, max) }}
      onPointer={onPointer}
    >
      <span role="group" aria-labelledby={labelId}>
        {([0, 1] as const).map((index) => (
          <Thumb
            key={index}
            thumbRef={(node) => {
              thumbs.current[index] = node;
            }}
            value={range[index]}
            percent={percentOf(range[index], min, max)}
            min={index === 0 ? min : low + minGap}
            max={index === 0 ? high - minGap : max}
            name={thumbLabels[index]}
            labelledBy={labelId}
            valueText={formatValue(range[index])}
            disabled={disabled}
            onKey={onKey(index)}
          />
        ))}
      </span>
    </SliderFrame>
  );
}
