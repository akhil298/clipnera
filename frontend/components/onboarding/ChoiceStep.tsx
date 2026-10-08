'use client';

import { Chip, Input } from '@/components/ui';

interface ChoiceStepProps<T extends string> {
  /** Names the chip group for screen readers. */
  label: string;
  options: readonly { value: T; label: string }[];
  selected: T | null;
  onSelect: (value: T) => void;
  /** Shown when "Other" is picked; the backend needs a few words then. */
  otherLabel: string;
  other: string;
  onOtherChange: (value: string) => void;
}

/** One required single choice of the welcome form, with a text field for "Other". */
export function ChoiceStep<T extends string>({ label, options, selected, onSelect, otherLabel, other, onOtherChange }: ChoiceStepProps<T>) {
  return (
    <div className="flex flex-col gap-4">
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
        {options.map((option, index) => (
          <Chip
            key={option.value}
            role="radio"
            aria-checked={selected === option.value}
            selected={selected === option.value}
            onClick={() => onSelect(option.value)}
            data-autofocus={index === 0 || undefined}
          >
            {option.label}
          </Chip>
        ))}
      </div>
      {selected === 'other' && <Input label={otherLabel} value={other} maxLength={80} onChange={(event) => onOtherChange(event.target.value)} autoFocus />}
    </div>
  );
}
