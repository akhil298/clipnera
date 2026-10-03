'use client';

import { CalendarClock, X } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { IconButton } from '@/components/ui/IconButton';
import { Kbd } from '@/components/ui/Kbd';

import { AppShell, type ShellOverlay } from '../_mock/AppShell';
import { ScreenFrame } from '../_mock/ScreenFrame';
import { SCREENS } from '../_mock/states';

const OVERLAYS: Record<string, ShellOverlay> = {
  notifications: 'notifications',
  'notifications-empty': 'notifications-empty',
  credits: 'credits',
  'credits-pending': 'credits-pending',
  activity: 'activity',
  command: 'command',
  'command-go': 'command-go',
  more: 'more',
};

const PARTS: Array<{ title: string; body: string }> = [
  { title: 'Sidebar', body: 'Home, Projects, then flag-gated Library, Reels and Scheduler, Brand kit, Settings. Recent projects with live percentages. Credits and the account menu (workspace switch, sign out) at the bottom. Collapses to a 64 px rail; the tablet rail expands over the page.' },
  { title: 'Header', body: 'Breadcrumb, the prompt entry (⌘K), the activity indicator (only while something runs), credits, notifications and New video. One amber action per view stays in the page, so header buttons are neutral.' },
  { title: 'Phone', body: 'Header keeps the wordmark, activity, credits and bell. A bottom tab bar holds Home, Projects, New video, one flag-chosen tab and More, which opens every page in a left drawer.' },
];

export function ShellMock({ state, theme }: { state: string; theme?: string }) {
  const banner =
    state === 'default' ? (
      <div className="flex items-center gap-3 border-t border-cn-border bg-cn-surface px-4 py-2 sm:px-6 lg:px-8">
        <CalendarClock aria-hidden className="size-4 shrink-0 text-cn-accent-text" />
        <p className="flex-1 text-cn-label text-cn-fg-secondary">Your Pro plan ends in 3 days. Pro doesn’t renew on its own.</p>
        <Button size="sm" variant="secondary">
          Renew Pro
        </Button>
        <IconButton label="Hide for now" icon={<X />} size="sm" />
      </div>
    ) : undefined;

  return (
    <ScreenFrame
      screen={SCREENS.shell.title}
      states={SCREENS.shell.states}
      state={state}
      theme={theme}
      note="Resize the window to see rail (768–1023 px) and phone (< 768 px) layouts. Each state opens one overlay; close it with Escape and focus returns to its trigger."
    >
      <AppShell
        active="projects"
        crumbs={[{ label: 'Projects', href: '#projects' }, { label: 'Episode 40 — The 3 a.m. routine' }]}
        overlay={OVERLAYS[state] ?? null}
        offline={state === 'offline'}
        rail={state === 'rail'}
        banner={banner}
      >
        <div className="flex flex-col gap-6">
          <div className="space-y-1">
            <h1 className="text-cn-title-lg font-bold">The app shell</h1>
            <p className="max-w-2xl text-cn-body text-cn-fg-secondary">
              Mounted once by the <code className="font-cn-mono text-cn-label">(app)/dashboard</code> layout; pages swap inside it with a 150 ms
              cross-fade and the shell never re-mounts. Press <Kbd keys={['⌘', 'K']} /> anywhere to ask Clipnera or jump to a page.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {PARTS.map((part) => (
              <Card key={part.title}>
                <CardHeader title={part.title} level={2} />
                <p className="mt-2 text-cn-body text-cn-fg-secondary">{part.body}</p>
              </Card>
            ))}
          </div>
        </div>
      </AppShell>
    </ScreenFrame>
  );
}
