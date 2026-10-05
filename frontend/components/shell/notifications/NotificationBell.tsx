'use client';

import { Bell } from 'lucide-react';
import { useState } from 'react';

import { IconButton } from '@/components/ui';

import { NotificationsDrawer } from './NotificationsDrawer';
import { useNotifications } from './useNotifications';

/** The header bell: its name carries the unread count; an amber dot marks unread items. */
export function NotificationBell() {
  const inbox = useNotifications();
  const [open, setOpen] = useState(false);
  const label = inbox.unread > 0 ? `Notifications, ${inbox.unread} unread` : 'Notifications';

  return (
    <>
      <span className="relative inline-flex">
        <IconButton label={label} icon={<Bell />} size="sm" aria-haspopup="dialog" onClick={() => setOpen(true)} />
        {inbox.unread > 0 && <span aria-hidden className="pointer-events-none absolute right-1 top-1 size-2 rounded-cn-full bg-cn-accent ring-2 ring-cn-bg" />}
      </span>
      <NotificationsDrawer open={open} onOpenChange={setOpen} inbox={inbox} />
    </>
  );
}
