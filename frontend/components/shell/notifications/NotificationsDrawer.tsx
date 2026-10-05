'use client';

import { Bell, CheckCheck } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Button, Drawer, EmptyState, InlineAlert, Skeleton, SkeletonGroup } from '@/components/ui';
import type { InAppNotification } from '@/lib/api/notifications';
import { cx, focusRing } from '@/lib/design/styles';
import { formatRelativeTime } from '@/lib/utils/dates';

import { BrowserNotifyPrompt } from './BrowserNotifyPrompt';
import { groupByDay, notificationHref, notificationIcon } from './notificationMeta';
import type { useNotifications } from './useNotifications';

type Inbox = ReturnType<typeof useNotifications>;

/** The current time, ticking once a minute while mounted, so "5 min ago" stays true. */
function useMinuteClock(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

function Row({ item, now, onOpen }: { item: InAppNotification; now: Date; onOpen: () => void }) {
  const unread = item.read_at === null;
  const href = notificationHref(item);
  const body = (
    <>
      <span aria-hidden className="mt-0.5 inline-flex shrink-0 [&_svg]:size-4">
        {notificationIcon(item.kind)}
      </span>
      <span className="min-w-0 flex-1">
        <span className={cx('block text-cn-label', unread ? 'font-semibold text-cn-fg' : 'text-cn-fg-secondary')}>
          {unread && <span className="sr-only">Unread: </span>}
          {item.title}
        </span>
        <span className="block text-cn-caption text-cn-fg-muted">{item.message}</span>
      </span>
      <time dateTime={item.created_at} className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">
        {formatRelativeTime(item.created_at, now)}
      </time>
      {unread && <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-cn-full bg-cn-accent" />}
    </>
  );
  const layout = 'flex items-start gap-3 rounded-cn-md px-2 py-2.5';

  return (
    <li>
      {href ? (
        <Link href={href} onClick={onOpen} className={cx(layout, 'hover:bg-cn-surface-hover active:bg-cn-surface-active', focusRing)}>
          {body}
        </Link>
      ) : (
        <div className={layout}>{body}</div>
      )}
    </li>
  );
}

function Loading() {
  return (
    <SkeletonGroup label="Loading notifications" className="flex flex-col gap-3">
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex items-start gap-3 px-2 py-2.5">
          <Skeleton className="size-4 rounded-cn-full" />
          <div className="flex flex-1 flex-col gap-1.5">
            <Skeleton className="h-4 w-3/5" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        </div>
      ))}
    </SkeletonGroup>
  );
}

/**
 * Right-hand inbox (screens/01 §5.2; full-height sheet on phones via Drawer).
 * Rows open their project, reel list or settings page and mark themselves read.
 */
export function NotificationsDrawer({ open, onOpenChange, inbox }: { open: boolean; onOpenChange: (open: boolean) => void; inbox: Inbox }) {
  const now = useMinuteClock();
  const { items, unread, loading, error } = inbox;
  const close = () => onOpenChange(false);

  let content;
  if (loading) content = <Loading />;
  else if (error && items.length === 0)
    content = (
      <InlineAlert
        tone="danger"
        title="I couldn’t load notifications"
        action={
          <Button size="sm" variant="secondary" onClick={inbox.retry}>
            Try again
          </Button>
        }
      >
        Nothing is lost; they’re still saved on our side.
      </InlineAlert>
    );
  else if (items.length === 0)
    content = (
      <EmptyState
        size="compact"
        level={3}
        icon={<Bell />}
        title="You’re all caught up"
        description="I’ll let you know here when clips are ready, an export finishes or a post goes out."
      />
    );
  else
    content = groupByDay(items, now).map((group) => (
      <section key={group.label} aria-label={group.label} className="flex flex-col gap-1">
        <h3 className="px-1 text-cn-caption text-cn-fg-muted">{group.label}</h3>
        <ul className="flex flex-col">
          {group.items.map((item) => (
            <Row
              key={item.id}
              item={item}
              now={now}
              onOpen={() => {
                inbox.open(item);
                close();
              }}
            />
          ))}
        </ul>
      </section>
    ));

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Notifications"
      description={unread > 0 ? `${unread} unread` : undefined}
      size="md"
      footer={
        items.length > 0 ? (
          <>
            <Button variant="ghost" size="sm" onClick={inbox.clearAll}>
              Clear all
            </Button>
            <Button
              variant="secondary"
              size="sm"
              leadingIcon={<CheckCheck />}
              disabled={unread === 0}
              loading={inbox.markingAll}
              loadingLabel="Marking read"
              onClick={inbox.markAllRead}
            >
              Mark all read
            </Button>
          </>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-4">
        {error && items.length > 0 && (
          <InlineAlert tone="neutral" live="status">
            I couldn’t refresh just now, so this is the last list I had. I’ll try again in a minute.
          </InlineAlert>
        )}
        {!loading && items.length > 0 && <BrowserNotifyPrompt />}
        {content}
      </div>
    </Drawer>
  );
}
