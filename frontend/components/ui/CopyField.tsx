'use client';

import { Check, Copy } from 'lucide-react';
import { type ReactNode, useRef } from 'react';

import { controlHeight, cx, fieldEdge } from '@/lib/design/styles';
import { useCopyToClipboard } from '@/lib/design/useCopyToClipboard';

import { Field } from './Field';
import { IconButton } from './IconButton';

export interface CopyFieldProps {
  value: string;
  label?: ReactNode;
  hint?: ReactNode;
  /** Accessible name when there is no visible label. */
  ariaLabel?: string;
  /** Show the value in mono (ids, keys, URLs). Default true. */
  mono?: boolean;
  /** Hide the value as dots (API keys) while keeping Copy. */
  masked?: boolean;
  onCopied?: () => void;
  className?: string;
}

/**
 * A read-only value with a Copy button: share links, request ids for support,
 * webhook URLs. Says "Copied" for 2 s; if the clipboard is blocked it selects
 * the text and says to press ⌘C.
 */
export function CopyField({ value, label, hint, ariaLabel, mono = true, masked = false, onCopied, className }: CopyFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const { state, copy } = useCopyToClipboard();
  const failed = state === 'failed';

  const onCopy = async () => {
    if (await copy(value)) onCopied?.();
    else inputRef.current?.select();
  };

  return (
    <Field label={label} hint={hint} error={failed ? 'Copy is blocked here. The text is selected: press ⌘C or Ctrl+C.' : undefined} className={className}>
      {({ inputId, describedBy }) => (
        <div className={cx('flex items-center gap-1 rounded-cn-md border pl-3 pr-0.5', controlHeight.md, fieldEdge({}))}>
          <input
            ref={inputRef}
            id={inputId}
            readOnly
            type={masked ? 'password' : 'text'}
            value={value}
            aria-label={label ? undefined : ariaLabel}
            aria-describedby={describedBy}
            onFocus={(event) => event.currentTarget.select()}
            className={cx(
              'h-full min-w-0 flex-1 truncate bg-transparent text-cn-fg focus-visible:outline-none',
              mono ? 'font-cn-mono text-cn-label' : 'text-cn-body',
            )}
          />
          <IconButton
            label={state === 'copied' ? 'Copied' : 'Copy'}
            icon={state === 'copied' ? <Check className="text-cn-success-text" /> : <Copy />}
            size="sm"
            onClick={onCopy}
          />
          <span role="status" className="sr-only">
            {state === 'copied' ? 'Copied to clipboard' : ''}
          </span>
        </div>
      )}
    </Field>
  );
}
