import type { ComponentPropsWithRef, ReactNode } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

export interface ChipProps extends Omit<ComponentPropsWithRef<'button'>, 'children'> {
  children: ReactNode;
  /**
   * Set for a filter or toggle chip (`aria-pressed`). Leave undefined for an
   * action chip such as a prompt suggestion, which fills the bar on click.
   */
  selected?: boolean;
  icon?: ReactNode;
  size?: 'sm' | 'md';
}

const SIZE = { sm: 'h-7 px-2.5 text-cn-caption gap-1.5', md: 'h-8 px-3 text-cn-label gap-1.5' } as const;

/** A compact button: filter chips, suggestion chips, next-step chips. */
export function Chip({ children, selected, icon, size = 'md', className, type = 'button', ...rest }: ChipProps) {
  return (
    <button
      type={type}
      aria-pressed={selected}
      className={cx(
        'inline-flex max-w-full shrink-0 items-center whitespace-nowrap rounded-cn-full border font-semibold [&_svg]:size-3.5',
        'transition-colors duration-cn-fast ease-cn-out disabled:cursor-not-allowed disabled:opacity-50',
        SIZE[size],
        selected
          ? 'border-cn-accent-border bg-cn-accent-subtle text-cn-accent-text'
          : 'border-cn-border-strong bg-cn-surface text-cn-fg-secondary hover:border-cn-control-border hover:text-cn-fg',
        focusRing,
        className,
      )}
      {...rest}
    >
      {icon && (
        <span aria-hidden className="inline-flex">
          {icon}
        </span>
      )}
      <span className="truncate">{children}</span>
    </button>
  );
}
