'use client';

import { CalendarClock, CircleAlert, Copy, FolderX, House, MapPinOff, RotateCcw } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { Button, buttonClasses } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton, SkeletonGroup, SkeletonText } from '@/components/ui/Skeleton';

import { AppShell } from '../_mock/AppShell';
import { ENTRY_BASE } from '../_mock/data';
import { ScreenFrame } from '../_mock/ScreenFrame';
import { Wordmark } from '../_mock/StandIns';
import { SCREENS } from '../_mock/states';

export function SystemMock({ state, theme }: { state: string; theme?: string }) {
  const frame = (children: ReactNode) => (
    <ScreenFrame
      screen={SCREENS.system.title}
      states={SCREENS.system.states}
      state={state}
      theme={theme}
      note="In-shell states keep the sidebar and header working, so one broken page never takes navigation with it. Skeletons appear only after 300 ms."
    >
      {children}
    </ScreenFrame>
  );

  if (state === 'global-error') {
    return frame(
      <main className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center">
        <Wordmark />
        <h1 className="mt-6 text-cn-title-lg font-bold">Clipnera didn’t load</h1>
        <p className="text-cn-body text-cn-fg-secondary">
          Something in this page stopped it from opening. Your projects and anything already running are safe on our side.
        </p>
        <Button leadingIcon={<RotateCcw />}>Reload</Button>
        <p className="font-cn-mono text-cn-caption text-cn-fg-muted">Reference 7f3a-91c2</p>
      </main>,
    );
  }

  if (state === 'public-404') {
    return frame(
      <main className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center">
        <Wordmark />
        <h1 className="mt-6 text-cn-title-lg font-bold">This page doesn’t exist</h1>
        <p className="text-cn-body text-cn-fg-secondary">The link may be old or mistyped.</p>
        <div className="flex flex-wrap justify-center gap-2">
          <Link href="/" className={buttonClasses()}>
            Go to the home page
          </Link>
          <Link href={`${ENTRY_BASE}/home`} className={buttonClasses({ variant: 'ghost' })}>
            Open my projects
          </Link>
        </div>
      </main>,
    );
  }

  let body: ReactNode;
  if (state === 'loading') {
    body = (
      <SkeletonGroup label="Loading Projects" className="flex flex-col gap-6">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex flex-col gap-2 rounded-cn-lg border border-cn-border p-3">
              <Skeleton className="aspect-video w-full" />
              <SkeletonText lines={2} />
            </div>
          ))}
        </div>
      </SkeletonGroup>
    );
  } else if (state === 'error') {
    body = (
      <Card padding="lg">
        <EmptyState
          icon={<CircleAlert />}
          title="This page didn’t load"
          description="I couldn’t get your projects just now. Nothing was lost, and work already running carries on."
          action={<Button leadingIcon={<RotateCcw />}>Try again</Button>}
          secondaryAction={
            <Button variant="ghost" leadingIcon={<Copy />}>
              Copy details for support
            </Button>
          }
        />
      </Card>
    );
  } else if (state === 'not-found') {
    body = (
      <Card padding="lg">
        <EmptyState
          icon={<MapPinOff />}
          title="This page doesn’t exist"
          description="The link may be old or mistyped. Everything else is where you left it."
          action={
            <Link href={`${ENTRY_BASE}/home`} className={buttonClasses({ variant: 'secondary' })}>
              <House aria-hidden className="size-4" />
              Go to Home
            </Link>
          }
        />
      </Card>
    );
  } else if (state === 'project-not-found') {
    body = (
      <Card padding="lg">
        <EmptyState
          icon={<FolderX />}
          title="Project not found"
          description="It may have been deleted, or it belongs to a workspace you’re not in. Check the workspace in the account menu."
          action={
            <Link href={`${ENTRY_BASE}/projects`} className={buttonClasses({ variant: 'secondary' })}>
              See all projects
            </Link>
          }
        />
      </Card>
    );
  } else {
    body = (
      <Card padding="lg">
        <EmptyState
          icon={<CalendarClock />}
          title="Scheduler isn’t on for your account yet"
          description="It’s being rolled out in stages. Until then you can download clips and post them yourself."
          action={
            <Link href={`${ENTRY_BASE}/projects`} className={buttonClasses({ variant: 'secondary' })}>
              Go to Projects
            </Link>
          }
        />
      </Card>
    );
  }

  const crumbs =
    state === 'flag-off'
      ? [{ label: 'Scheduler' }]
      : state === 'project-not-found'
        ? [{ label: 'Projects', href: `${ENTRY_BASE}/projects` }, { label: 'Not found' }]
        : [{ label: 'Projects' }];

  return frame(
    <AppShell active={state === 'flag-off' ? 'scheduler' : 'projects'} crumbs={crumbs}>
      <div className="mx-auto max-w-5xl">
        {state !== 'loading' && <h1 className="sr-only">{state === 'flag-off' ? 'Scheduler' : 'Projects'}</h1>}
        {body}
      </div>
    </AppShell>,
  );
}
