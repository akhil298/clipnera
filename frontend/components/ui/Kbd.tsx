import { Fragment } from 'react';

import { cx } from '@/lib/design/styles';

/** Spoken names for symbols a screen reader would otherwise skip or mispronounce. */
const SPOKEN: Record<string, string> = {
  '⌘': 'Command',
  '⇧': 'Shift',
  '⌥': 'Option',
  '⌃': 'Control',
  '↵': 'Enter',
  '⌫': 'Delete',
  '⎋': 'Escape',
  '↑': 'Up arrow',
  '↓': 'Down arrow',
  '←': 'Left arrow',
  '→': 'Right arrow',
};

export interface KbdProps {
  /** One key per entry, pressed together: `['⌘', 'K']`. */
  keys: readonly string[];
  className?: string;
}

/** A keyboard shortcut, e.g. in a menu item, tooltip or the shortcuts dialog. */
export function Kbd({ keys, className }: KbdProps) {
  return (
    <kbd className={cx('inline-flex items-center gap-0.5 font-cn-sans', className)}>
      {keys.map((key, index) => (
        <Fragment key={`${key}-${index}`}>
          <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded-cn-xs border border-cn-border-strong bg-cn-surface px-1 font-cn-mono text-cn-caption font-medium text-cn-fg-secondary shadow-[inset_0_-1px_0_rgb(var(--cn-border-strong))]">
            {SPOKEN[key] ? (
              <>
                <span aria-hidden>{key}</span>
                <span className="sr-only">{SPOKEN[key]}</span>
              </>
            ) : (
              key
            )}
          </kbd>
          {index < keys.length - 1 && <span className="sr-only"> plus </span>}
        </Fragment>
      ))}
    </kbd>
  );
}
