import { CalendarClock, CircleAlert, CircleCheck, Coins, RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';

import type { InAppNotification, NotificationKind } from '@/lib/api/notifications';
import { BILLING_HREF } from '@/components/shell/nav';
import { parseApiDate } from '@/lib/utils/dates';

const SOCIAL_HREF = '/dashboard/settings/social';

/** Icon tone by meaning (screens/01 §5.2): ready = success, failed = danger, credits = accent, reconnect = neutral. */
const ICON: Record<NotificationKind, ReactNode> = {
  pipeline_completed: <CircleCheck className="text-cn-success-text" />,
  reel_ready: <CircleCheck className="text-cn-success-text" />,
  pipeline_failed: <CircleAlert className="text-cn-danger-text" />,
  reel_failed: <CircleAlert className="text-cn-danger-text" />,
  payment_approved: <Coins className="text-cn-accent-text" />,
  social_expiring: <CalendarClock className="text-cn-info-text" />,
  social_expired: <RefreshCw className="text-cn-fg-secondary" />,
};

export const notificationIcon = (kind: NotificationKind): ReactNode => ICON[kind];

/** Where opening a notification goes; null when there is nothing to open (the row is plain text). */
export function notificationHref(item: InAppNotification): string | null {
  switch (item.kind) {
    case 'pipeline_completed':
    case 'pipeline_failed':
      return item.project_id ? `/dashboard/projects/${item.project_id}` : null;
    case 'reel_ready':
    case 'reel_failed':
      return '/dashboard/reels';
    case 'payment_approved':
      return BILLING_HREF;
    case 'social_expiring':
    case 'social_expired':
      return SOCIAL_HREF;
  }
}

export const isFailure = (item: InAppNotification) => item.kind === 'pipeline_failed' || item.kind === 'reel_failed';

/** "Today" and "Earlier" in the viewer's own day; empty groups are dropped. */
export function groupByDay(items: readonly InAppNotification[], now: Date) {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const today = items.filter((item) => parseApiDate(item.created_at).getTime() >= startOfToday);
  const earlier = items.filter((item) => parseApiDate(item.created_at).getTime() < startOfToday);
  return [
    { label: 'Today', items: today },
    { label: 'Earlier', items: earlier },
  ].filter((group) => group.items.length > 0);
}
