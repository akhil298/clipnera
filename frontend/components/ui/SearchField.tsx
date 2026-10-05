'use client';

import { Search, X } from 'lucide-react';
import { type ComponentPropsWithRef, type KeyboardEvent, type ReactNode, useRef } from 'react';

import { mergeRefs } from '@/lib/design/refs';
import type { ControlSize } from '@/lib/design/styles';

import { LoadingSweep } from './Button';
import { IconButton } from './IconButton';
import { Input } from './Input';
import { Kbd } from './Kbd';

export interface SearchFieldProps
  extends Omit<ComponentPropsWithRef<'input'>, 'size' | 'value' | 'defaultValue' | 'onChange' | 'type'> {
  value: string;
  onValueChange: (value: string) => void;
  /** Visible label; omit in toolbars and pass `aria-label` (defaults to "Search"). */
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  size?: ControlSize;
  /** Results are loading: a thin sweep under the field. Typing stays allowed. */
  loading?: boolean;
  /** Hint keys shown while empty, e.g. `['/']`. Display only; wire the shortcut elsewhere. */
  shortcut?: readonly string[];
  /** Enter. Live-filtering lists can ignore it. */
  onSearch?: (value: string) => void;
  className?: string;
}

/**
 * Search input with a leading icon and a Clear button. Escape clears the text
 * first; a second Escape bubbles to whatever is around it (closing a panel).
 */
export function SearchField({
  value,
  onValueChange,
  label,
  hint,
  error,
  size = 'md',
  loading = false,
  shortcut,
  onSearch,
  placeholder = 'Search',
  className,
  ref,
  onKeyDown,
  ...rest
}: SearchFieldProps) {
  const innerRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    onKeyDown?.(event);
    if (event.defaultPrevented || event.nativeEvent.isComposing) return;
    if (event.key === 'Escape' && value) {
      event.preventDefault();
      event.stopPropagation();
      onValueChange('');
    } else if (event.key === 'Enter') {
      onSearch?.(value);
    }
  };

  const clear = () => {
    onValueChange('');
    innerRef.current?.focus();
  };

  return (
    <div role="search" className={['relative', className].filter(Boolean).join(' ')}>
      <Input
        ref={mergeRefs(innerRef, ref)}
        type="search"
        size={size}
        label={label}
        hint={hint}
        error={error}
        aria-label={label ? undefined : (rest['aria-label'] ?? 'Search')}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        leading={<Search />}
        trailing={
          value ? (
            <IconButton label="Clear search" icon={<X />} size="sm" tooltip={false} onClick={clear} className="-mr-2" />
          ) : (
            shortcut && <Kbd keys={shortcut} />
          )
        }
        className="[&_input::-webkit-search-cancel-button]:appearance-none"
        {...rest}
      />
      {loading && <LoadingSweep className="rounded-b-cn-md text-cn-accent" />}
    </div>
  );
}
