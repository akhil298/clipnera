import type { ComponentPropsWithRef, ReactNode } from 'react';

import { cx, focusRing, type ControlSize } from '@/lib/design/styles';

import { LoadingSweep } from './Button';
import { Tooltip } from './Tooltip';

export type IconButtonVariant = 'ghost' | 'secondary' | 'primary' | 'danger';

const VARIANT: Record<IconButtonVariant, string> = {
  ghost: 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active',
  secondary:
    'border border-cn-control-border bg-cn-surface text-cn-fg hover:bg-cn-surface-hover active:bg-cn-surface-active',
  primary: 'bg-cn-accent text-cn-accent-fg hover:bg-cn-accent-hover active:bg-cn-accent-pressed',
  danger: 'text-cn-danger-text hover:bg-cn-danger-subtle',
};

const SIZE: Record<ControlSize, string> = {
  sm: 'size-8 rounded-cn-sm [&_svg]:size-4',
  md: 'size-9 rounded-cn-md [&_svg]:size-[18px]',
  lg: 'size-11 rounded-cn-md [&_svg]:size-5',
};

export interface IconButtonProps extends Omit<ComponentPropsWithRef<'button'>, 'children' | 'aria-label'> {
  /** Accessible name, also shown as the tooltip. Required: an icon alone has no name. */
  label: string;
  icon: ReactNode;
  variant?: IconButtonVariant;
  size?: ControlSize;
  /** Toggle buttons (mute, loop): sets `aria-pressed` and the selected look. */
  pressed?: boolean;
  loading?: boolean;
  /** Show the label as a tooltip. Default true. */
  tooltip?: boolean;
}

export function IconButton({
  label,
  icon,
  variant = 'ghost',
  size = 'md',
  pressed,
  loading = false,
  tooltip = true,
  className,
  type = 'button',
  onClick,
  ...rest
}: IconButtonProps) {
  const button = (
    <button
      type={type}
      aria-label={label}
      aria-pressed={pressed}
      aria-busy={loading || undefined}
      aria-disabled={loading || undefined}
      onClick={loading ? (event) => event.preventDefault() : onClick}
      className={cx(
        'relative inline-flex shrink-0 items-center justify-center overflow-hidden',
        'transition-[background-color,color,transform] duration-cn-fast ease-cn-out motion-safe:active:scale-95',
        'disabled:pointer-events-none disabled:opacity-50',
        focusRing,
        SIZE[size],
        VARIANT[variant],
        pressed && 'bg-cn-accent-subtle text-cn-accent-text hover:bg-cn-accent-subtle hover:text-cn-accent-text',
        className,
      )}
      {...rest}
    >
      <span aria-hidden className="inline-flex">
        {icon}
      </span>
      {loading && <LoadingSweep />}
    </button>
  );
  return tooltip ? (
    <Tooltip content={label} asLabel>
      {button}
    </Tooltip>
  ) : (
    button
  );
}
