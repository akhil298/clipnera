import type { ComponentPropsWithRef, ReactNode } from 'react';

import { cx, focusWithinRing } from '@/lib/design/styles';

const PADDING = { none: '', sm: 'p-3', md: 'p-4', lg: 'p-6' } as const;

export interface CardProps extends ComponentPropsWithRef<'div'> {
  padding?: keyof typeof PADDING;
  /**
   * Hover lift and a focus ring when anything inside has focus. Put one real
   * link or button inside (add `cardLinkOverlay` to it for a whole-card hit area);
   * the card itself is never the click target.
   */
  interactive?: boolean;
  selected?: boolean;
}

/** A bordered surface that groups one thing: a project, a plan, a setting group. */
export function Card({ padding = 'md', interactive = false, selected = false, className, ...rest }: CardProps) {
  return (
    <div
      className={cx(
        'relative rounded-cn-lg border bg-cn-surface text-cn-fg',
        PADDING[padding],
        selected ? 'border-cn-accent-border' : 'border-cn-border',
        interactive &&
          cx(
            'transition-[border-color,box-shadow] duration-cn-fast ease-cn-out hover:border-cn-border-strong hover:shadow-cn-1',
            focusWithinRing,
          ),
        className,
      )}
      {...rest}
    />
  );
}

export interface CardHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  /** Buttons or a menu on the right. */
  actions?: ReactNode;
  /** Heading level for the title; match the page outline. Default 3. */
  level?: 2 | 3 | 4;
  className?: string;
}

export function CardHeader({ title, description, actions, level = 3, className }: CardHeaderProps) {
  const Heading = `h${level}` as const;
  return (
    <div className={cx('flex items-start justify-between gap-3', className)}>
      <div className="min-w-0 space-y-1">
        <Heading className="text-cn-title-sm font-semibold text-cn-fg">{title}</Heading>
        {description && <p className="text-cn-body text-cn-fg-secondary">{description}</p>}
      </div>
      {actions && <div className="relative z-cn-raised flex shrink-0 items-center gap-1">{actions}</div>}
    </div>
  );
}

export function CardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('mt-4 flex items-center justify-end gap-2 border-t border-cn-border pt-4', className)}>{children}</div>;
}

/**
 * Makes the whole card clickable through one real link: the link's
 * `::after` covers the card. Other buttons in the card sit above it (`z-cn-raised`).
 */
export const cardLinkOverlay = "after:absolute after:inset-0 after:rounded-cn-lg after:content-[''] focus-visible:outline-none";
