'use client';

import { useId } from 'react';

import type { LogoPosition } from '@/lib/api/brand/types';
import { cx, focusRing } from '@/lib/design/styles';

import { LOGO_POSITIONS } from '../options';

/** The watermark corner as a 2 × 2 mini screen. Native radios: one Tab stop, arrows move and select. */
export function PositionPicker({ value, onValueChange }: { value: LogoPosition; onValueChange: (value: LogoPosition) => void }) {
  const name = useId();
  return (
    <fieldset className="min-w-0 space-y-2">
      <legend className="mb-2 text-cn-label font-semibold text-cn-fg">Watermark position</legend>
      <div className="grid w-32 grid-cols-2 gap-1.5 rounded-cn-lg border border-cn-border bg-cn-surface-sunken p-1.5 aspect-cn-portrait">
        {LOGO_POSITIONS.map((position) => {
          const checked = position.value === value;
          return (
            <label
              key={position.value}
              title={position.label}
              className={cx(
                'flex cursor-pointer rounded-cn-md p-2 transition-colors duration-cn-fast ease-cn-standard',
                position.value.startsWith('top') ? 'items-start' : 'items-end',
                position.value.endsWith('left') ? 'justify-start' : 'justify-end',
                checked ? 'bg-cn-surface-active ring-2 ring-inset ring-cn-accent-border' : 'bg-cn-surface hover:bg-cn-surface-hover',
              )}
            >
              <input
                type="radio"
                name={name}
                value={position.value}
                checked={checked}
                onChange={() => onValueChange(position.value)}
                aria-label={position.label}
                className={cx(
                  'size-4 shrink-0 appearance-none rounded-cn-xs border',
                  checked ? 'border-cn-accent bg-cn-accent' : 'border-cn-control-border bg-cn-field',
                  focusRing,
                )}
              />
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
