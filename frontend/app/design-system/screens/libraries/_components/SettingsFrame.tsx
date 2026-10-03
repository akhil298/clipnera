'use client';

import { Bell, CreditCard, Plug, User, Users } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { AppShell, PageBody, ScreenHeader } from './Shells';

export const SETTINGS_SECTIONS = [
  { id: 'account', label: 'Account and privacy', icon: <User /> },
  { id: 'workspace', label: 'Workspace and team', icon: <Users /> },
  { id: 'billing', label: 'Plan and billing', icon: <CreditCard /> },
  { id: 'notifications', label: 'Notifications', icon: <Bell /> },
  { id: 'connections', label: 'Connected accounts', icon: <Plug /> },
] as const;

export type SettingsSection = (typeof SETTINGS_SECTIONS)[number]['id'];

/**
 * Settings shell: `/dashboard/settings/<section>`. A 224 px section list on
 * desktop; a scrolling row of links on tablet and phone. Links change the URL
 * (path segments), so this is navigation with `aria-current`, not tabs.
 * `/dashboard/settings?tab=billing|social|team` 308-redirects here
 * (social → connections, team → workspace).
 */
export function SettingsFrame({ section, children, hideConnections }: { section: SettingsSection; children: ReactNode; hideConnections?: boolean }) {
  const items = SETTINGS_SECTIONS.filter((s) => !(hideConnections && s.id === 'connections'));
  return (
    <AppShell active="settings">
      <PageBody>
        <ScreenHeader title="Settings" description="Your account, workspace, plan and the accounts you publish to." />
        <div className="flex flex-col gap-6 lg:flex-row lg:gap-10">
          <nav aria-label="Settings sections" className="lg:w-56 lg:shrink-0">
            <ul className="flex gap-1 overflow-x-auto pb-1 lg:sticky lg:top-6 lg:flex-col lg:overflow-visible">
              {items.map((s) => {
                const current = s.id === section;
                return (
                  <li key={s.id} className="shrink-0">
                    <a
                      href="#"
                      onClick={(e) => e.preventDefault()}
                      aria-current={current ? 'page' : undefined}
                      className={cx(
                        'flex h-9 items-center gap-2.5 whitespace-nowrap rounded-cn-md px-3 text-cn-body [&_svg]:size-4',
                        current ? 'bg-cn-surface-active font-semibold text-cn-fg' : 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg',
                        focusRing,
                      )}
                    >
                      <span aria-hidden className={current ? 'text-cn-accent-text' : undefined}>
                        {s.icon}
                      </span>
                      {s.label}
                    </a>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="min-w-0 max-w-3xl flex-1 space-y-6">{children}</div>
        </div>
      </PageBody>
    </AppShell>
  );
}

/** One settings group: heading level 2, optional description and actions, then content. */
export function SettingsCard({ title, description, actions, children, danger, id }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; children?: ReactNode; danger?: boolean; id?: string }) {
  const headingId = id ?? `card-${String(title).toLowerCase().replace(/[^a-z]+/g, '-')}`;
  return (
    <section aria-labelledby={headingId} className={cx('rounded-cn-lg border bg-cn-surface p-4 sm:p-6', danger ? 'border-cn-danger/40' : 'border-cn-border')}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h2 id={headingId} className="text-cn-title-sm font-semibold text-cn-fg">
            {title}
          </h2>
          {description && <p className="max-w-xl text-cn-body text-cn-fg-secondary">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </section>
  );
}
