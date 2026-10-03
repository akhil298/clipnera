'use client';

import {
  BarChart3,
  CalendarClock,
  Coins,
  CreditCard,
  Film,
  Flag,
  FolderOpen,
  Home,
  Library,
  Menu as MenuIcon,
  Palette,
  Settings,
  Share2,
  SlidersHorizontal,
  Users,
} from 'lucide-react';
import type { ReactNode } from 'react';

import { Badge } from '@/components/ui/Badge';
import { IconButton } from '@/components/ui/IconButton';
import { cx, focusRing } from '@/lib/design/styles';

const APP_NAV = [
  { id: 'home', label: 'Home', icon: <Home /> },
  { id: 'projects', label: 'Projects', icon: <FolderOpen /> },
  { id: 'library', label: 'Library', icon: <Library /> },
  { id: 'reels', label: 'Reels', icon: <Film /> },
  { id: 'scheduler', label: 'Scheduler', icon: <CalendarClock /> },
  { id: 'brand-kit', label: 'Brand kit', icon: <Palette /> },
  { id: 'settings', label: 'Settings', icon: <Settings /> },
] as const;

export type AppNavId = (typeof APP_NAV)[number]['id'];

function NavItem({ label, icon, active }: { label: string; icon: ReactNode; active: boolean }) {
  return (
    <a
      href="#"
      onClick={(e) => e.preventDefault()}
      aria-current={active ? 'page' : undefined}
      className={cx(
        'flex h-9 items-center gap-2.5 rounded-cn-md px-2.5 text-cn-body [&_svg]:size-4',
        active ? 'bg-cn-surface-active font-semibold text-cn-fg' : 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg',
        focusRing,
      )}
    >
      <span aria-hidden className={active ? 'text-cn-accent-text' : undefined}>
        {icon}
      </span>
      {label}
    </a>
  );
}

/**
 * Placeholder of the new app shell so screens sit in context. The shell itself
 * is Designer 1's; only its presence and width matter here (240 px rail on
 * desktop, a top bar below 1024 px).
 */
export function AppShell({ active, children }: { active: AppNavId; children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside aria-label="Main" className="hidden w-60 shrink-0 border-r border-cn-border bg-cn-surface px-3 py-4 lg:block">
        <p className="mb-4 px-2.5 font-cn-display text-cn-title-sm font-bold tracking-tight">clipnera</p>
        <nav aria-label="Main">
          <ul className="space-y-0.5">
            {APP_NAV.map((item) => (
              <li key={item.id}>
                <NavItem label={item.label} icon={item.icon} active={item.id === active} />
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-2 border-b border-cn-border px-4 lg:hidden">
          <IconButton label="Open navigation" icon={<MenuIcon />} />
          <span className="font-cn-display text-cn-title-sm font-bold tracking-tight">clipnera</span>
        </header>
        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}

const ADMIN_NAV = [
  { id: 'overview', label: 'Overview', icon: <BarChart3 /> },
  { id: 'users', label: 'Users', icon: <Users /> },
  { id: 'payments', label: 'Payments', icon: <CreditCard /> },
  { id: 'credits', label: 'Credits', icon: <Coins /> },
  { id: 'social', label: 'Social', icon: <Share2 /> },
  { id: 'usage', label: 'AI usage', icon: <BarChart3 /> },
  { id: 'broll', label: 'B-roll library', icon: <Library /> },
  { id: 'flags', label: 'Feature flags', icon: <Flag /> },
  { id: 'config', label: 'Remote config', icon: <SlidersHorizontal /> },
] as const;

export type AdminNavId = (typeof ADMIN_NAV)[number]['id'];

/** The admin shell, mounted once in `app/v2/(admin)/admin/layout.tsx`. */
export function AdminShell({ active, children }: { active: AdminNavId; children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside aria-label="Admin" className="hidden w-60 shrink-0 border-r border-cn-border bg-cn-surface px-3 py-4 lg:block">
        <p className="mb-4 flex items-center gap-2 px-2.5">
          <span className="font-cn-display text-cn-title-sm font-bold tracking-tight">clipnera</span>
          <Badge>Admin</Badge>
        </p>
        <nav aria-label="Admin">
          <ul className="space-y-0.5">
            {ADMIN_NAV.map((item) => (
              <li key={item.id}>
                <NavItem label={item.label} icon={item.icon} active={item.id === active} />
              </li>
            ))}
          </ul>
        </nav>
        <p className="mt-6 px-2.5 text-cn-caption text-cn-fg-muted">Signed in as a@clipnera.com · superadmin</p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <nav aria-label="Admin" className="flex gap-1 overflow-x-auto border-b border-cn-border px-4 py-2 lg:hidden">
          {ADMIN_NAV.map((item) => (
            <a
              key={item.id}
              href="#"
              onClick={(e) => e.preventDefault()}
              aria-current={item.id === active ? 'page' : undefined}
              className={cx(
                'inline-flex h-8 shrink-0 items-center rounded-cn-full px-3 text-cn-label',
                item.id === active ? 'bg-cn-surface-active font-semibold text-cn-fg' : 'text-cn-fg-secondary hover:bg-cn-surface-hover',
                focusRing,
              )}
            >
              {item.label}
            </a>
          ))}
        </nav>
        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}

/** Page title block used by every screen in this set (title-lg, description, actions). */
export function ScreenHeader({
  title,
  description,
  actions,
  meta,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0 space-y-1">
        <h1 className="text-cn-title lg:text-cn-title-lg font-bold text-cn-fg">{title}</h1>
        {description && <p className="max-w-2xl text-cn-body text-cn-fg-secondary">{description}</p>}
        {meta}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Page gutter and max width (16 / 24 / 32 px; 1280 px max). */
export function PageBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('mx-auto w-full max-w-screen-xl space-y-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8', className)}>{children}</div>;
}

/**
 * Section navigation that changes the URL (path segments), so it is a `nav`
 * of links with `aria-current`, styled like underline tabs. In-page views use
 * `Tabs` instead.
 */
export function NavTabs({
  label,
  items,
  active,
  onSelect,
}: {
  label: string;
  items: ReadonlyArray<{ id: string; label: ReactNode; count?: number }>;
  active: string;
  onSelect?: (id: string) => void;
}) {
  return (
    <nav aria-label={label} className="flex gap-5 overflow-x-auto border-b border-cn-border">
      {items.map((item) => {
        const current = item.id === active;
        return (
          <a
            key={item.id}
            href="#"
            onClick={(e) => {
              e.preventDefault();
              onSelect?.(item.id);
            }}
            aria-current={current ? 'page' : undefined}
            className={cx(
              'relative inline-flex h-10 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-cn-xs text-cn-body font-semibold',
              current ? 'text-cn-fg' : 'text-cn-fg-secondary hover:text-cn-fg',
              focusRing,
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span className="rounded-cn-full bg-cn-surface-hover px-1.5 font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary">
                {item.count}
              </span>
            )}
            {current && <span aria-hidden className="absolute inset-x-0 -bottom-px h-0.5 rounded-cn-full bg-cn-accent" />}
          </a>
        );
      })}
    </nav>
  );
}
