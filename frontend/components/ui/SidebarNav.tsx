'use client';

import Link from 'next/link';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { createContext, type ReactNode, useContext } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { IconButton } from './IconButton';
import { Tooltip } from './Tooltip';

const RailContext = createContext(false);

/** True inside a collapsed Sidebar: items hide their labels and show tooltips. */
export const useSidebarCollapsed = () => useContext(RailContext);

export interface SidebarProps {
  /** Landmark name of the navigation inside: "Main", "Admin". */
  label: string;
  /** 56px icon rail instead of the 240px sidebar. Persist it with `usePersistentState`. */
  collapsed?: boolean;
  /** Shows the collapse toggle in the header. */
  onCollapsedChange?: (collapsed: boolean) => void;
  /** Top row: the wordmark (switch it to `LogoMark` alone when collapsed). */
  header?: ReactNode;
  /** Pinned bottom: credits, AvatarMenu. */
  footer?: ReactNode;
  children: ReactNode;
  /** Full viewport height, sticky (default). False fills the parent instead (previews, nested layouts). */
  fullHeight?: boolean;
  className?: string;
}

/**
 * The app's left sidebar: header, scrolling navigation, pinned footer. Shown
 * from `md` (add `hidden md:flex` at the call site); phones use MobileTabBar.
 * Width changes over `slow` (280 ms), instantly under reduced motion.
 */
export function Sidebar({ label, collapsed = false, onCollapsedChange, header, footer, children, fullHeight = true, className }: SidebarProps) {
  return (
    <RailContext.Provider value={collapsed}>
      <aside
        aria-label="Sidebar"
        className={cx(
          'flex shrink-0 flex-col border-r border-cn-border bg-cn-surface',
          fullHeight ? 'sticky top-0 h-dvh' : 'h-full',
          'motion-safe:transition-[width] motion-safe:duration-cn-slow motion-safe:ease-cn-in-out',
          collapsed ? 'w-14' : 'w-60',
          className,
        )}
      >
        {(header || onCollapsedChange) && (
          <div className={cx('flex shrink-0 items-center px-3', collapsed ? 'flex-col justify-center gap-1 px-2 py-2' : 'h-12 gap-2')}>
            {header}
            {onCollapsedChange && (
              <>
                {!collapsed && <span className="flex-1" />}
                <IconButton
                  size="sm"
                  label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                  icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
                  aria-expanded={!collapsed}
                  onClick={() => onCollapsedChange(!collapsed)}
                />
              </>
            )}
          </div>
        )}
        <nav aria-label={label} className={cx('flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto overflow-x-hidden py-2', collapsed ? 'px-2' : 'px-3')}>
          {children}
        </nav>
        {footer && <div className="flex shrink-0 flex-col gap-3 border-t border-cn-border p-3">{footer}</div>}
      </aside>
    </RailContext.Provider>
  );
}

export interface SidebarSectionProps {
  /** Small heading ("Recent", "Workspace"). Hidden in the rail; the list keeps it as its name. */
  title?: string;
  children: ReactNode;
  className?: string;
}

/** A group of SidebarNavItems. */
export function SidebarSection({ title, children, className }: SidebarSectionProps) {
  const collapsed = useSidebarCollapsed();
  return (
    <div className={cx('flex flex-col gap-1', className)}>
      {title && <p className={cx('px-2.5 text-cn-caption text-cn-fg-muted', collapsed && 'sr-only')}>{title}</p>}
      <ul aria-label={title} className="flex flex-col gap-0.5">
        {children}
      </ul>
    </div>
  );
}

export interface SidebarNavItemProps {
  label: string;
  icon: ReactNode;
  /** Navigates with next/link. Omit and pass `onClick` for an action (open search). */
  href?: string;
  onClick?: () => void;
  /** The current page: `aria-current="page"`, raised fill and an amber icon. */
  active?: boolean;
  /** A count after the label ("3" unread); a dot in the rail. */
  count?: number;
  /** Extra trailing content in the expanded sidebar (a percent, a Badge). */
  trailing?: ReactNode;
  disabled?: boolean;
}

/** One sidebar row: icon and label; in the rail, the icon with a tooltip that also names it. */
export function SidebarNavItem({ label, icon, href, onClick, active = false, count, trailing, disabled = false }: SidebarNavItemProps) {
  const collapsed = useSidebarCollapsed();
  const className = cx(
    'relative flex h-9 items-center gap-3 rounded-cn-md text-left text-cn-body transition-colors duration-cn-fast [&_svg]:size-4',
    collapsed ? 'w-10 justify-center' : 'w-full px-2.5',
    active
      ? 'bg-cn-surface-active font-semibold text-cn-fg'
      : 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active',
    disabled && 'pointer-events-none opacity-50',
    focusRing,
  );
  const hasCount = count !== undefined && count > 0;
  const content = (
    <>
      <span aria-hidden className={cx('inline-flex shrink-0', active && 'text-cn-accent-text')}>
        {icon}
      </span>
      <span className={cx('min-w-0 flex-1 truncate', collapsed && 'sr-only')}>{label}</span>
      {hasCount &&
        (collapsed ? (
          <span className="absolute right-2 top-1.5 size-2 rounded-cn-full bg-cn-accent">
            <span className="sr-only">, {count} new</span>
          </span>
        ) : (
          <span className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">
            {count}
            <span className="sr-only"> new</span>
          </span>
        ))}
      {!collapsed && trailing}
    </>
  );

  const element = href ? (
    <Link href={href} aria-current={active ? 'page' : undefined} aria-disabled={disabled || undefined} onClick={onClick} className={className}>
      {content}
    </Link>
  ) : (
    <button type="button" disabled={disabled} onClick={onClick} className={className}>
      {content}
    </button>
  );

  return (
    <li>
      {collapsed ? (
        <Tooltip content={label} side="right">
          {element}
        </Tooltip>
      ) : (
        element
      )}
    </li>
  );
}
