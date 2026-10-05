import type { ComponentPropsWithRef, ReactNode } from 'react';

import { type ControlSize, controlHeight, cx, focusRing } from '@/lib/design/styles';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-cn-accent text-cn-accent-fg hover:bg-cn-accent-hover active:bg-cn-accent-pressed',
  secondary:
    'border border-cn-control-border bg-cn-surface text-cn-fg hover:bg-cn-surface-hover active:bg-cn-surface-active',
  ghost: 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active',
  danger: 'bg-cn-danger-solid text-cn-on-danger hover:bg-cn-danger-solid-hover',
};

const SIZE: Record<ControlSize, string> = {
  sm: 'px-3 gap-1.5 text-cn-label rounded-cn-sm [&_svg]:size-3.5',
  md: 'px-3.5 gap-2 text-cn-body rounded-cn-md [&_svg]:size-4',
  lg: 'px-5 gap-2 text-cn-body-lg rounded-cn-md [&_svg]:size-[18px]',
};

export interface ButtonStyleOptions {
  variant?: ButtonVariant;
  size?: ControlSize;
  fullWidth?: boolean;
}

/**
 * Button classes without the element, for a Next `<Link>` that should look
 * like a button: `<Link className={buttonClasses({ variant: 'secondary' })}>`.
 */
export function buttonClasses({ variant = 'primary', size = 'md', fullWidth = false }: ButtonStyleOptions = {}): string {
  return cx(
    'relative inline-flex select-none items-center justify-center overflow-hidden whitespace-nowrap font-semibold',
    'transition-[background-color,border-color,color,transform] duration-cn-fast ease-cn-out motion-safe:active:scale-[0.98]',
    'disabled:pointer-events-none disabled:opacity-50 aria-disabled:cursor-not-allowed',
    focusRing,
    controlHeight[size],
    SIZE[size],
    VARIANT[variant],
    fullWidth && 'w-full',
  );
}

/** A thin bar sweeping along the bottom edge: the loading state without a spinner. */
export function LoadingSweep({ className }: { className?: string }) {
  return (
    <span aria-hidden className={cx('pointer-events-none absolute inset-x-0 bottom-0 h-0.5 overflow-hidden', className)}>
      <span className="absolute inset-y-0 left-0 w-2/5 bg-current opacity-60 motion-safe:animate-cn-sweep motion-reduce:w-full motion-reduce:opacity-30" />
    </span>
  );
}

export interface ButtonProps extends Omit<ComponentPropsWithRef<'button'>, 'children'>, ButtonStyleOptions {
  children: ReactNode;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  /** Busy: keeps focus, ignores clicks, shows `loadingLabel` and a sweeping bar. */
  loading?: boolean;
  /** Present tense, e.g. "Saving". Defaults to the normal label. */
  loadingLabel?: ReactNode;
}

export function Button({
  variant,
  size,
  fullWidth,
  leadingIcon,
  trailingIcon,
  loading = false,
  loadingLabel,
  className,
  type = 'button',
  onClick,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      aria-busy={loading || undefined}
      aria-disabled={loading || undefined}
      onClick={loading ? (event) => event.preventDefault() : onClick}
      className={cx(buttonClasses({ variant, size, fullWidth }), className)}
      {...rest}
    >
      {leadingIcon && <span aria-hidden className="inline-flex shrink-0">{leadingIcon}</span>}
      <span className="truncate">{loading && loadingLabel ? loadingLabel : children}</span>
      {trailingIcon && <span aria-hidden className="inline-flex shrink-0">{trailingIcon}</span>}
      {loading && <LoadingSweep />}
    </button>
  );
}
