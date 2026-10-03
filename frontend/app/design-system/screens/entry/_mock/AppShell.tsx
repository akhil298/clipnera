'use client';

import {
  Bell,
  BellRing,
  CalendarClock,
  ChartColumn,
  CheckCheck,
  CircleAlert,
  CircleCheck,
  Clapperboard,
  Coins,
  FolderOpen,
  House,
  Library,
  LogOut,
  Menu as MenuIcon,
  Palette,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  Search,
  Settings,
  WifiOff,
} from 'lucide-react';
import Link from 'next/link';
import { type ReactNode, useState } from 'react';

import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Drawer } from '@/components/ui/Drawer';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconButton } from '@/components/ui/IconButton';
import { Kbd } from '@/components/ui/Kbd';
import { LogoMark } from '@/components/ui/LogoMark';
import { Menu } from '@/components/ui/Menu';
import { Popover } from '@/components/ui/Popover';
import { PromptBar, type PromptMode } from '@/components/ui/PromptBar';
import { cx, focusRing } from '@/lib/design/styles';

import { credits, ENTRY_BASE, jobs as sampleJobs, notifications, type NotificationKind, projects, user, workspaces } from './data';
import { ActivityIndicator, Avatar, CreditMeter, SlashMenuList, Wordmark } from './StandIns';

export type NavKey = 'home' | 'projects' | 'library' | 'reels' | 'scheduler' | 'brand' | 'settings' | 'analytics';

export type ShellOverlay =
  | 'notifications'
  | 'notifications-empty'
  | 'credits'
  | 'credits-pending'
  | 'activity'
  | 'command'
  | 'command-go'
  | 'more'
  | null;

const NAV: Array<{ key: NavKey; label: string; icon: ReactNode; href: string; flag?: string }> = [
  { key: 'home', label: 'Home', icon: <House />, href: `${ENTRY_BASE}/home` },
  { key: 'projects', label: 'Projects', icon: <FolderOpen />, href: `${ENTRY_BASE}/projects` },
  { key: 'library', label: 'Library', icon: <Library />, href: '#library', flag: 'broll_platform_library' },
  { key: 'reels', label: 'Reels', icon: <Clapperboard />, href: '#reels', flag: 'broll_studio.reels' },
  { key: 'scheduler', label: 'Scheduler', icon: <CalendarClock />, href: '#scheduler', flag: 'social_publishing' },
  { key: 'brand', label: 'Brand kit', icon: <Palette />, href: '#brand-kit' },
  { key: 'settings', label: 'Settings', icon: <Settings />, href: '#settings' },
];

/** Analytics stays hidden until real data exists (owner default); shown here only to mark where it would go. */
const ANALYTICS = { key: 'analytics' as const, label: 'Analytics', icon: <ChartColumn />, href: '#analytics' };

const NOTIFICATION_ICON: Record<NotificationKind, ReactNode> = {
  clips_ready: <CircleCheck className="text-cn-success-text" />,
  failed: <CircleAlert className="text-cn-danger-text" />,
  scheduled: <CalendarClock className="text-cn-info-text" />,
  credits: <Coins className="text-cn-accent-text" />,
  reconnect: <RefreshCw className="text-cn-fg-secondary" />,
};

export interface AppShellProps {
  active: NavKey;
  /** Breadcrumb trail; the last item is the current page. */
  crumbs: ReadonlyArray<{ label: string; href?: string }>;
  children: ReactNode;
  overlay?: ShellOverlay;
  /** Server jobs for the activity indicator. */
  jobs?: ReadonlyArray<{ id: string; project: string; label: string; percent?: number }>;
  offline?: boolean;
  /** Collapsed rail at desktop widths. */
  rail?: boolean;
  /** Hide the header prompt entry and New video (Home: the hero is both). */
  hidePromptEntry?: boolean;
  /** A strip under the header: plan banner, offline, reconnecting. */
  banner?: ReactNode;
}

/**
 * The signed-in frame (one tree for every width, so no duplicate ids):
 * sidebar ≥ md (rail 64 px at md, 256 px ≥ lg, collapsible), sticky header,
 * phone tab bar < md. Overlays open from `overlay` so each state can be shown.
 */
export function AppShell({
  active,
  crumbs,
  children,
  overlay = null,
  jobs = sampleJobs,
  offline = false,
  rail = false,
  hidePromptEntry = false,
  banner,
}: AppShellProps) {
  const [collapsed, setCollapsed] = useState(rail);
  const [tabletOpen, setTabletOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(overlay === 'notifications' || overlay === 'notifications-empty');
  const [commandOpen, setCommandOpen] = useState(overlay === 'command' || overlay === 'command-go');
  const [moreOpen, setMoreOpen] = useState(overlay === 'more');
  const [command, setCommand] = useState(overlay === 'command-go' ? '/go epis' : '');
  const [mode, setMode] = useState<PromptMode>('edit');
  const unread = overlay === 'notifications-empty' ? 0 : notifications.filter((item) => !item.read).length;
  const labelClass = cx(tabletOpen ? 'not-sr-only' : 'sr-only', !collapsed && 'lg:not-sr-only');

  const navList = (onNavigate?: () => void, showLabels = false) => (
    <ul className="flex flex-col gap-0.5">
      {NAV.map((item) => (
        <li key={item.key}>
          <Link
            href={item.href}
            onClick={onNavigate}
            aria-current={item.key === active ? 'page' : undefined}
            className={cx(
              'flex h-9 items-center gap-3 rounded-cn-md px-2.5 text-cn-body [&_svg]:size-4',
              item.key === active
                ? 'bg-cn-surface-active font-semibold text-cn-fg [&_svg]:text-cn-accent-text'
                : 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg',
              focusRing,
            )}
          >
            <span aria-hidden className="inline-flex shrink-0">
              {item.icon}
            </span>
            <span className={showLabels ? '' : labelClass}>{item.label}</span>
          </Link>
        </li>
      ))}
    </ul>
  );

  const accountMenu = (
    <Menu
      align="start"
      side="top"
      items={[
        { type: 'label', id: 'who', label: user.email },
        { type: 'separator', id: 's0' },
        { type: 'label', id: 'ws', label: 'Workspace' },
        ...workspaces.map((ws) => ({ id: ws.id, label: ws.name, checked: ws.current, onSelect: () => undefined })),
        { type: 'separator', id: 's1' },
        { id: 'settings', label: 'Settings', icon: <Settings />, onSelect: () => undefined },
        { id: 'shortcuts', label: 'Keyboard shortcuts', shortcut: ['?'], onSelect: () => undefined },
        { type: 'separator', id: 's2' },
        { id: 'signout', label: 'Sign out', icon: <LogOut />, onSelect: () => undefined },
      ]}
      trigger={(props) => (
        <button
          type="button"
          {...props}
          aria-label={`Account: ${user.name}`}
          className={cx('flex w-full items-center gap-2.5 rounded-cn-md p-1.5 text-left hover:bg-cn-surface-hover', focusRing)}
        >
          <Avatar initials={user.initials} />
          <span className={cx('min-w-0 flex-1', labelClass)}>
            <span className="block truncate text-cn-label font-semibold text-cn-fg">{user.name}</span>
            <span className="block truncate text-cn-caption text-cn-fg-muted">
              {user.plan} · {user.workspace}
            </span>
          </span>
        </button>
      )}
    />
  );

  return (
    <div className="flex min-h-screen bg-cn-bg text-cn-fg">
      <a
        href="#main"
        className="fixed left-4 top-2 z-cn-skiplink -translate-y-16 rounded-cn-md bg-cn-accent px-3 py-2 text-cn-label font-semibold text-cn-accent-fg focus:translate-y-0"
      >
        Skip to content
      </a>

      {/* Sidebar: one tree. Rail at md, full at lg; the tablet rail expands over the page. */}
      <aside
        aria-label="Sidebar"
        className={cx(
          'sticky top-0 z-cn-sticky hidden h-screen shrink-0 flex-col border-r border-cn-border bg-cn-surface md:flex',
          tabletOpen ? 'w-64 shadow-cn-3 lg:shadow-none' : collapsed ? 'w-16' : 'w-16 lg:w-64',
          'transition-[width] duration-cn-base ease-cn-in-out',
        )}
      >
        <div className="flex h-14 items-center gap-2 px-3">
          <Link href={`${ENTRY_BASE}/home`} aria-label="Clipnera home" className={cx('rounded-cn-sm', focusRing)}>
            <span className="inline-flex items-center gap-2">
              <LogoMark size={24} />
              <span className={cx('font-cn-display text-cn-body-lg font-bold tracking-tight text-cn-fg', labelClass)}>clipnera</span>
            </span>
          </Link>
          <span className="flex-1" />
          <IconButton
            size="sm"
            label={collapsed || !tabletOpen ? 'Expand sidebar' : 'Collapse sidebar'}
            icon={tabletOpen || !collapsed ? <PanelLeftClose /> : <PanelLeftOpen />}
            className="lg:hidden"
            onClick={() => setTabletOpen(!tabletOpen)}
          />
          <IconButton
            size="sm"
            label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            className="hidden lg:inline-flex"
            onClick={() => setCollapsed(!collapsed)}
          />
        </div>
        <nav aria-label="Main" className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-3 py-2">
          {navList()}
          <div className={cx('flex flex-col gap-1', labelClass)}>
            <p className="px-2.5 text-cn-caption text-cn-fg-muted">Recent</p>
            <ul className="flex flex-col gap-0.5">
              {projects.slice(0, 4).map((project) => (
                <li key={project.id}>
                  <Link
                    href={project.state === 'ready' ? '#clips' : `${ENTRY_BASE}/progress?state=running`}
                    className={cx(
                      'flex min-h-8 items-center gap-2 rounded-cn-sm px-2.5 py-1 text-cn-label text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg',
                      focusRing,
                    )}
                  >
                    <span className="min-w-0 flex-1 truncate">{project.title}</span>
                    {(project.state === 'processing' || project.state === 'uploading') && (
                      <span className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-accent-text">{project.percent}%</span>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div className={cx('rounded-cn-md border border-dashed border-cn-border-strong p-2.5', labelClass)}>
            <div className="flex items-center gap-2 text-cn-label text-cn-fg-muted">
              <ChartColumn aria-hidden className="size-4" />
              {ANALYTICS.label}
              <Badge>Hidden by flag</Badge>
            </div>
          </div>
        </nav>
        <div className="flex flex-col gap-3 border-t border-cn-border p-3">
          <div className={labelClass}>
            <CreditMeter plan={credits.plan} planTotal={credits.planTotal} packs={credits.packs} compact />
          </div>
          {accountMenu}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-cn-sticky border-b border-cn-border bg-cn-bg/90 backdrop-blur">
          <div className="flex h-14 items-center gap-2 px-4 sm:px-6 lg:px-8">
            <Link href={`${ENTRY_BASE}/home`} aria-label="Clipnera home" className={cx('rounded-cn-sm md:hidden', focusRing)}>
              <Wordmark size="sm" />
            </Link>
            <nav aria-label="Breadcrumb" className="hidden min-w-0 md:block">
              <ol className="flex items-center gap-1.5 text-cn-label">
                {crumbs.map((crumb, index) => {
                  const last = index === crumbs.length - 1;
                  return (
                    <li key={crumb.label} className="flex min-w-0 items-center gap-1.5">
                      {index > 0 && <span aria-hidden className="text-cn-fg-disabled">/</span>}
                      {last || !crumb.href ? (
                        <span aria-current={last ? 'page' : undefined} className="truncate font-semibold text-cn-fg">
                          {crumb.label}
                        </span>
                      ) : (
                        <Link href={crumb.href} className={cx('truncate rounded-cn-xs text-cn-fg-secondary hover:text-cn-fg', focusRing)}>
                          {crumb.label}
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>
            <span className="flex-1" />
            {!hidePromptEntry && (
              <button
                type="button"
                onClick={() => setCommandOpen(true)}
                aria-keyshortcuts="Meta+K Control+K"
                className={cx(
                  'hidden h-8 w-72 items-center gap-2 rounded-cn-md border border-cn-control-border bg-cn-field px-2.5 text-cn-label text-cn-fg-muted hover:border-cn-fg-muted lg:flex',
                  focusRing,
                )}
              >
                <Search aria-hidden className="size-4" />
                <span className="flex-1 text-left">Ask Clipnera, or type / to go</span>
                <Kbd keys={['⌘', 'K']} />
              </button>
            )}
            {!hidePromptEntry && (
              <IconButton label="Ask Clipnera or go to a page" icon={<Search />} size="sm" className="lg:hidden" onClick={() => setCommandOpen(true)} />
            )}
            <ActivityIndicator jobs={jobs} defaultOpen={overlay === 'activity'} />
            <Popover
              title="Credits"
              align="end"
              defaultOpen={overlay === 'credits' || overlay === 'credits-pending'}
              trigger={(props) => (
                <Button {...props} variant="ghost" size="sm" leadingIcon={<Coins />} aria-label={`${credits.balance.toLocaleString('en-IN')} credits`}>
                  <span className="font-cn-mono tabular-nums">{credits.balance.toLocaleString('en-IN')}</span>
                </Button>
              )}
            >
              <div className="flex flex-col gap-3">
                <CreditMeter plan={credits.plan} planTotal={credits.planTotal} packs={credits.packs} />
                <dl className="flex flex-col gap-1 text-cn-caption">
                  {[
                    ['Plan credits renew', credits.renews],
                    ['Pack credits', 'Never expire'],
                    ['Held for work in progress', String(credits.held)],
                  ].map(([term, value]) => (
                    <div key={term} className="flex justify-between gap-3">
                      <dt className="text-cn-fg-secondary">{term}</dt>
                      <dd className="text-cn-fg">{value}</dd>
                    </div>
                  ))}
                </dl>
                {overlay === 'credits-pending' && (
                  <p className="rounded-cn-md border border-cn-info/30 bg-cn-info-subtle p-2.5 text-cn-caption text-cn-info-text">
                    Your UPI payment for 200 credits is being checked. I’ll add them and let you know once it’s approved.
                  </p>
                )}
                <div className="flex gap-2">
                  <Button size="sm" className="flex-1">
                    Add credits
                  </Button>
                  <Button size="sm" variant="ghost">
                    See plans
                  </Button>
                </div>
              </div>
            </Popover>
            <span className="relative inline-flex">
              <IconButton label={unread ? `Notifications, ${unread} unread` : 'Notifications'} icon={<Bell />} size="sm" onClick={() => setNotificationsOpen(true)} />
              {unread > 0 && (
                <span aria-hidden className="pointer-events-none absolute right-1 top-1 size-2 rounded-cn-full bg-cn-accent ring-2 ring-cn-bg" />
              )}
            </span>
            {!hidePromptEntry && (
              <Button variant="secondary" size="sm" leadingIcon={<Plus />} className="hidden md:inline-flex">
                New video
              </Button>
            )}
          </div>
          {offline && (
            <div role="status" className="flex items-center gap-2 border-t border-cn-border bg-cn-surface px-4 py-2 text-cn-label text-cn-fg-secondary sm:px-6 lg:px-8">
              <WifiOff aria-hidden className="size-4 shrink-0" />
              You’re offline. Work already started keeps going on our side; this page catches up when you’re back.
            </div>
          )}
          {banner}
        </header>

        <main id="main" tabIndex={-1} className="min-w-0 flex-1 px-4 pb-28 pt-6 focus-visible:outline-none sm:px-6 md:pb-12 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">{children}</div>
        </main>
      </div>

      {/* Phone tab bar: the centre action is subtle amber so the page's primary keeps the fill. */}
      <nav aria-label="Main, phone" className="fixed inset-x-0 bottom-0 z-cn-sticky border-t border-cn-border bg-cn-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        <ul className="grid h-16 grid-cols-5">
          {[NAV[0], NAV[1]].map((item) => (
            <li key={item.key}>
              <Link
                href={item.href}
                aria-current={item.key === active ? 'page' : undefined}
                className={cx(
                  'flex h-full flex-col items-center justify-center gap-1 text-cn-caption [&_svg]:size-5',
                  item.key === active ? 'text-cn-accent-text' : 'text-cn-fg-muted',
                  focusRing,
                )}
              >
                <span aria-hidden>{item.icon}</span>
                {item.label}
              </Link>
            </li>
          ))}
          <li className="flex items-center justify-center">
            <button
              type="button"
              aria-label="New video"
              className={cx('inline-flex size-11 items-center justify-center rounded-cn-full border border-cn-accent-border bg-cn-accent-subtle text-cn-accent-text', focusRing)}
            >
              <Plus aria-hidden className="size-5" />
            </button>
          </li>
          <li>
            <Link href="#scheduler" className={cx('flex h-full flex-col items-center justify-center gap-1 text-cn-caption text-cn-fg-muted [&_svg]:size-5', focusRing)}>
              <span aria-hidden>
                <CalendarClock />
              </span>
              Schedule
            </Link>
          </li>
          <li>
            <button
              type="button"
              onClick={() => setMoreOpen(true)}
              className={cx('flex h-full w-full flex-col items-center justify-center gap-1 text-cn-caption text-cn-fg-muted [&_svg]:size-5', focusRing)}
            >
              <MenuIcon aria-hidden />
              More
            </button>
          </li>
        </ul>
      </nav>

      <Drawer
        open={notificationsOpen}
        onOpenChange={setNotificationsOpen}
        title="Notifications"
        description={unread ? `${unread} unread` : undefined}
        size="md"
        footer={
          unread || overlay === 'notifications' ? (
            <>
              <Button variant="ghost" size="sm">
                Clear all
              </Button>
              <Button variant="secondary" size="sm" leadingIcon={<CheckCheck />}>
                Mark all read
              </Button>
            </>
          ) : undefined
        }
      >
        {overlay === 'notifications-empty' ? (
          <EmptyState
            size="compact"
            icon={<Bell />}
            title="You’re all caught up"
            description="I’ll let you know here when clips are ready, an export finishes or a post goes out."
          />
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-start gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3">
              <BellRing aria-hidden className="mt-0.5 size-4 shrink-0 text-cn-fg-secondary" />
              <div className="flex-1 space-y-2">
                <p className="text-cn-label text-cn-fg">Get a browser notification when clips are ready, even with this tab closed.</p>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary">
                    Turn on
                  </Button>
                  <Button size="sm" variant="ghost">
                    Not now
                  </Button>
                </div>
              </div>
            </div>
            {(['Today', 'Earlier'] as const).map((group) => (
              <section key={group} aria-label={group} className="flex flex-col gap-1">
                <h3 className="px-1 text-cn-caption text-cn-fg-muted">{group}</h3>
                <ul className="flex flex-col">
                  {notifications
                    .filter((item) => item.group === group)
                    .map((item) => (
                      <li key={item.id}>
                        <a
                          href="#open"
                          className={cx('flex items-start gap-3 rounded-cn-md px-2 py-2.5 hover:bg-cn-surface-hover', focusRing)}
                        >
                          <span aria-hidden className="mt-0.5 inline-flex shrink-0 [&_svg]:size-4">
                            {NOTIFICATION_ICON[item.kind]}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className={cx('block text-cn-label', item.read ? 'text-cn-fg-secondary' : 'font-semibold text-cn-fg')}>
                              {!item.read && <span className="sr-only">Unread: </span>}
                              {item.title}
                            </span>
                            <span className="block text-cn-caption text-cn-fg-muted">{item.message}</span>
                          </span>
                          <span className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{item.time}</span>
                          {!item.read && <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-cn-full bg-cn-accent" />}
                        </a>
                      </li>
                    ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </Drawer>

      <Dialog
        open={commandOpen}
        onOpenChange={setCommandOpen}
        title="Ask Clipnera"
        description="Describe what you want, or type / for commands and /go to jump to a page."
        size="lg"
      >
        <div className="flex flex-col gap-3">
          {command.startsWith('/go') ? (
            <SlashMenuList
              label="Go to"
              rows={[
                { id: 'p1', group: 'Projects', command: 'Episode 41', description: 'Transcribing · 46%', icon: <FolderOpen /> },
                { id: 'p3', group: 'Projects', command: 'Episode 40', description: '9 clips', icon: <FolderOpen /> },
                { id: 'p6', group: 'Projects', command: 'Episode 39', description: '11 clips', icon: <FolderOpen /> },
                { id: 'g1', group: 'Pages', command: 'Projects', description: 'All projects and folders', icon: <FolderOpen /> },
                { id: 'g2', group: 'Pages', command: 'Settings', description: 'Plan, credits, connected accounts', icon: <Settings /> },
              ]}
            />
          ) : (
            <SlashMenuList
              rows={[
                { id: 'clips', group: 'Make', command: '/clips', description: 'Find the best moments in a video' },
                { id: 'captions', group: 'Make', command: '/captions', description: 'Add or restyle captions' },
                { id: 'trim', group: 'Make', command: '/trim', description: 'Remove silences, fillers, retakes' },
                { id: 'go', group: 'Go to', command: '/go', description: 'Projects, settings, library, a project by name' },
              ]}
            />
          )}
          <PromptBar
            value={command}
            onValueChange={setCommand}
            onSubmit={() => setCommandOpen(false)}
            mode={mode}
            onModeChange={setMode}
            onAttach={() => undefined}
            label="Ask Clipnera or type a command"
          />
          <p className="text-cn-caption text-cn-fg-muted">
            <Kbd keys={['↑']} /> <Kbd keys={['↓']} /> to choose · <Kbd keys={['↵']} /> to fill · <Kbd keys={['⎋']} /> to close. Nothing runs until you press send.
          </p>
        </div>
      </Dialog>

      <Drawer open={moreOpen} onOpenChange={setMoreOpen} title="Menu" side="left" size="sm">
        <nav aria-label="All pages" className="flex flex-col gap-6">
          {navList(() => setMoreOpen(false), true)}
          <CreditMeter plan={credits.plan} planTotal={credits.planTotal} packs={credits.packs} />
          <div className="border-t border-cn-border pt-3">{accountMenu}</div>
        </nav>
      </Drawer>
    </div>
  );
}

/** A status line for a project's live step, used by cards and rows. */
export function LiveStatus({ state, step }: { state: string; step?: string }) {
  if (state === 'ready') return <StatusBadge status="ready" />;
  if (state === 'failed') return <StatusBadge status="failed" />;
  if (state === 'cancelled') return <StatusBadge status="paused">Stopped</StatusBadge>;
  if (state === 'awaiting_credits') return <StatusBadge status="paused">Waiting for credits</StatusBadge>;
  return <StatusBadge status="processing">{step ?? 'Processing'}</StatusBadge>;
}
