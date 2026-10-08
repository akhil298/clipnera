import Link from 'next/link';
import type { ReactNode } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

export interface MobileTab {
  id: string;
  label: string;
  icon: ReactNode;
  /** Navigates; omit and pass `onClick` for an action tab ("More" opening a Drawer). */
  href?: string;
  onClick?: () => void;
  /** Unread or waiting count; a dot plus a spoken count. */
  count?: number;
  /** The centre "New (+)" action: its icon sits on an amber-subtle circle. One per bar. */
  emphasis?: boolean;
}

export interface MobileTabBarProps {
  /** Landmark name: "Main". */
  label: string;
  /** Up to five tabs. */
  items: ReadonlyArray<MobileTab>;
  activeId?: string;
  /** `inline` renders it in the flow at every width (previews, the editor's phone frame). Default `fixed`. */
  placement?: 'fixed' | 'inline';
  className?: string;
}

/**
 * Bottom navigation for phones (< md): 56px plus the home-indicator inset,
 * fixed at `z-cn-sticky`. Give the page `pb-16` so content clears it.
 */
export function MobileTabBar({ label, items, activeId, placement = 'fixed', className }: MobileTabBarProps) {
  return (
    <nav
      aria-label={label}
      className={cx(
        'border-t border-cn-border bg-cn-bg pb-safe',
        placement === 'fixed' && 'fixed inset-x-0 bottom-0 z-cn-sticky md:hidden',
        className,
      )}
    >
      <ul className="flex">
        {items.slice(0, 5).map((item) => {
          const active = item.id === activeId;
          const itemClass = cx(
            'relative flex h-14 w-full flex-col items-center justify-center gap-0.5 text-cn-caption transition-colors duration-cn-fast [&_svg]:size-5',
            active ? 'font-semibold text-cn-fg' : 'text-cn-fg-muted hover:text-cn-fg active:bg-cn-surface-hover',
            focusRing,
            'focus-visible:-outline-offset-2',
          );
          const content = (
            <>
              <span
                aria-hidden
                className={cx(
                  'relative inline-flex',
                  item.emphasis && 'size-8 items-center justify-center rounded-cn-full bg-cn-accent-subtle text-cn-accent-text',
                  active && 'text-cn-accent-text',
                )}
              >
                {item.icon}
                {item.count !== undefined && item.count > 0 && (
                  <span className="absolute -right-1 -top-0.5 size-2 rounded-cn-full bg-cn-accent ring-2 ring-cn-bg" />
                )}
              </span>
              <span className="max-w-full truncate px-1">{item.label}</span>
              {item.count !== undefined && item.count > 0 && <span className="sr-only">, {item.count} new</span>}
            </>
          );
          return (
            <li key={item.id} className="min-w-0 flex-1">
              {item.href ? (
                <Link href={item.href} aria-current={active ? 'page' : undefined} onClick={item.onClick} className={itemClass}>
                  {content}
                </Link>
              ) : (
                <button type="button" onClick={item.onClick} className={itemClass}>
                  {content}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
