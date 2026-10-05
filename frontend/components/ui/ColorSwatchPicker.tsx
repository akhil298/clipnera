'use client';

import { Check } from 'lucide-react';
import { type KeyboardEvent, type ReactNode, useId, useRef, useState } from 'react';

import { cx, focusRing, focusWithinRing } from '@/lib/design/styles';
import { colors } from '@/lib/design/tokens';
import { useControllableState } from '@/lib/design/useControllableState';

import { Input } from './Input';

export interface Swatch {
  /** `#rrggbb`. */
  value: string;
  /** Spoken and shown on hover: "Amber". */
  name: string;
}

/** The palette a person may pick from: the token hues only (amber, emerald, rose, sky) plus neutrals. */
export const TOKEN_SWATCHES: ReadonlyArray<Swatch> = [
  { value: colors.dark.accent, name: 'Amber' },
  { value: colors.dark['accent-hover'], name: 'Light amber' },
  { value: colors.dark.success, name: 'Emerald' },
  { value: colors.dark.danger, name: 'Rose' },
  { value: colors.dark.info, name: 'Sky' },
  { value: colors.dark.fg, name: 'White' },
  { value: colors.dark['fg-muted'], name: 'Grey' },
  { value: colors.dark.bg, name: 'Black' },
];

const HEX = /^#[0-9a-f]{6}$/i;
const normalise = (hex: string) => hex.trim().toLowerCase();

export interface ColorSwatchPickerProps {
  label: ReactNode;
  value?: string;
  defaultValue?: string;
  onValueChange?: (hex: string) => void;
  swatches?: ReadonlyArray<Swatch>;
  /** Brand Kit: adds a "Brand colour" swatch with a colour picker and a hex field. */
  allowCustom?: boolean;
  customLabel?: string;
  hint?: ReactNode;
  disabled?: boolean;
  className?: string;
}

/**
 * Pick one colour: caption highlight, accent for a template, a brand colour.
 * A radio group of swatches (arrows move and select); the selected one has a
 * tick, not just a ring, so the choice never rests on colour alone.
 */
export function ColorSwatchPicker({
  label,
  value,
  defaultValue,
  onValueChange,
  swatches = TOKEN_SWATCHES,
  allowCustom = false,
  customLabel = 'Brand colour',
  hint,
  disabled = false,
  className,
}: ColorSwatchPickerProps) {
  const id = useId();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const [current, setCurrent] = useControllableState(value, defaultValue ?? swatches[0].value, onValueChange);
  const selected = normalise(current);
  const inPalette = swatches.some((swatch) => normalise(swatch.value) === selected);
  const [draft, setDraft] = useState(inPalette ? '' : current);
  const [draftError, setDraftError] = useState<string>();

  const options: Swatch[] = [...swatches, ...(allowCustom ? [{ value: inPalette ? draft || '#000000' : current, name: customLabel }] : [])];
  const selectedIndex = inPalette ? swatches.findIndex((swatch) => normalise(swatch.value) === selected) : allowCustom ? options.length - 1 : -1;

  const choose = (index: number) => {
    const option = options[index];
    if (!option || disabled) return;
    setCurrent(option.value);
    refs.current[index]?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (!(event.key in moves)) return;
    event.preventDefault();
    const from = Math.max(selectedIndex, 0);
    choose((from + moves[event.key] + options.length) % options.length);
  };

  const commitDraft = (text: string) => {
    setDraft(text);
    const hex = text.startsWith('#') ? text : `#${text}`;
    if (HEX.test(hex)) {
      setDraftError(undefined);
      setCurrent(normalise(hex));
    } else {
      setDraftError('Use six hex digits, like #f59e0b.');
    }
  };

  const customSelected = allowCustom && !inPalette;

  return (
    <div className={cx('flex flex-col gap-2', className)}>
      <span id={`${id}-label`} className="text-cn-label font-semibold text-cn-fg">
        {label}
      </span>
      <div role="radiogroup" aria-labelledby={`${id}-label`} aria-describedby={hint ? `${id}-hint` : undefined} onKeyDown={onKeyDown} className="flex flex-wrap gap-2">
        {options.map((option, index) => {
          const isSelected = index === selectedIndex;
          const custom = allowCustom && index === options.length - 1;
          return (
            <button
              key={custom ? 'custom' : option.value}
              ref={(node) => {
                refs.current[index] = node;
              }}
              type="button"
              role="radio"
              aria-checked={isSelected}
              aria-label={custom ? `${customLabel}${customSelected ? `, ${current}` : ''}` : option.name}
              title={option.name}
              tabIndex={isSelected || (selectedIndex < 0 && index === 0) ? 0 : -1}
              disabled={disabled}
              onClick={() => choose(index)}
              className={cx(
                'relative inline-flex size-8 items-center justify-center rounded-cn-full border border-cn-border-strong',
                'transition-transform duration-cn-fast ease-cn-out motion-safe:hover:scale-110 motion-safe:active:scale-95',
                'disabled:cursor-not-allowed disabled:opacity-50',
                isSelected && 'ring-2 ring-cn-fg ring-offset-2 ring-offset-cn-bg',
                custom && !customSelected && 'border-dashed border-cn-control-border',
                focusRing,
              )}
              style={custom && !customSelected ? undefined : { backgroundColor: option.value }}
            >
              {isSelected && (
                <span aria-hidden className="inline-flex size-4 items-center justify-center rounded-cn-full bg-cn-bg/70 text-cn-fg">
                  <Check className="size-3" strokeWidth={3} />
                </span>
              )}
              {custom && !customSelected && <span aria-hidden className="text-cn-label font-semibold text-cn-fg-muted">+</span>}
            </button>
          );
        })}
      </div>
      {customSelected && (
        <div className="flex items-start gap-2">
          <label className={cx('relative inline-flex size-9 shrink-0 cursor-pointer overflow-hidden rounded-cn-md border border-cn-control-border', focusWithinRing)}>
            <span className="sr-only">Pick {customLabel.toLowerCase()}</span>
            <input
              type="color"
              value={HEX.test(current) ? current : '#000000'}
              disabled={disabled}
              onChange={(event) => commitDraft(event.target.value)}
              className="absolute inset-0 size-full cursor-pointer opacity-0"
            />
            <span aria-hidden className="size-full" style={{ backgroundColor: current }} />
          </label>
          <Input
            aria-label={`${customLabel} hex value`}
            value={draft || current}
            onChange={(event) => commitDraft(event.target.value)}
            error={draftError}
            disabled={disabled}
            spellCheck={false}
            maxLength={7}
            className="w-32 font-cn-mono"
          />
        </div>
      )}
      {hint && (
        <p id={`${id}-hint`} className="text-cn-caption text-cn-fg-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
