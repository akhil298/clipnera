'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { notificationsApi, type InAppNotificationResponse } from '@/lib/api';
import type { AppNotification } from '@/lib/types';

// Reconnect delays after the stream drops: doubles up to the cap.
const RETRY_MIN_MS = 2000;
const RETRY_MAX_MS = 60000;

function timeAgo(iso: string): string {
  // The backend stores naive UTC timestamps, so pin them to UTC before parsing.
  const created = new Date(/[zZ]|[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`).getTime();
  const minutes = Math.floor((Date.now() - created) / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
}

const TYPE_BY_KIND: Record<InAppNotificationResponse['kind'], AppNotification['type']> = {
  pipeline_completed: 'render_complete',
  pipeline_failed: 'render_failed',
  payment_approved: 'credit_update',
  reel_ready: 'render_complete',
  reel_failed: 'render_failed',
  social_expiring: 'scheduled_post',
  social_expired: 'scheduled_post',
};

function toAppNotification(n: InAppNotificationResponse): AppNotification {
  return {
    id: n.id,
    title: n.title,
    message: n.message,
    type: TYPE_BY_KIND[n.kind],
    timestamp: timeAgo(n.created_at),
    read: n.read_at !== null,
    projectId: n.project_id ?? undefined,
  };
}

/** The user's notifications: server-side ones plus local, session-only ones.
 * New server notifications are pushed over SSE; `onArrive` fires once for each
 * one that shows up after the first load, which is what the snackbar listens to. */
export function useNotificationInbox(enabled: boolean, onArrive: (notification: AppNotification) => void) {
  const [serverNotifications, setServerNotifications] = useState<AppNotification[]>([]);
  const [localNotifications, setLocalNotifications] = useState<AppNotification[]>([]);
  // null until the first load, whose unread backlog shows in the drawer badge
  // rather than as a burst of snackbars.
  const seenIds = useRef<Set<string> | null>(null);
  const onArriveRef = useRef(onArrive);
  onArriveRef.current = onArrive;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let unsubscribe: (() => void) | null = null;
    let retryId: ReturnType<typeof setTimeout> | null = null;
    let retryMs = RETRY_MIN_MS;

    const announce = (arrived: AppNotification[]) => {
      if (!seenIds.current) return;
      const fresh = arrived.filter((n) => !n.read && !seenIds.current!.has(n.id));
      fresh.forEach((n) => seenIds.current!.add(n.id));
      fresh.forEach((n) => onArriveRef.current(n));
    };

    // The list is the source of truth: loaded on every (re)connect, it picks up
    // anything created while the stream was down.
    const sync = async () => {
      const { notifications } = await notificationsApi.list();
      if (cancelled) return;
      const mapped = notifications.map(toAppNotification);
      const firstLoad = seenIds.current === null;
      if (firstLoad) seenIds.current = new Set(mapped.map((n) => n.id));
      else announce([...mapped].reverse());
      setServerNotifications(mapped);
    };

    const connect = () => {
      unsubscribe = notificationsApi.subscribe(
        (event) => {
          retryMs = RETRY_MIN_MS;
          const notification = toAppNotification(event);
          setServerNotifications((prev) => [notification, ...prev.filter((n) => n.id !== notification.id)]);
          announce([notification]);
        },
        (err) => {
          if (cancelled || err.message === 'Session expired' || err.message === 'Not authenticated') return;
          retryId = setTimeout(connect, retryMs);
          retryMs = Math.min(retryMs * 2, RETRY_MAX_MS);
        },
      );
      sync().catch((err) => console.error('Failed to load notifications:', err));
    };

    connect();
    return () => {
      cancelled = true;
      unsubscribe?.();
      if (retryId) clearTimeout(retryId);
    };
  }, [enabled]);

  const pushLocal = useCallback((notification: AppNotification) => {
    setLocalNotifications((prev) => [notification, ...prev]);
  }, []);

  const markAllRead = useCallback(async () => {
    setLocalNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setServerNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    try {
      const { notifications } = await notificationsApi.markAllRead();
      setServerNotifications(notifications.map(toAppNotification));
    } catch (err) {
      console.error('Failed to mark notifications as read:', err);
    }
  }, []);

  const clearAll = useCallback(async () => {
    setLocalNotifications([]);
    setServerNotifications([]);
    try {
      await notificationsApi.clear();
    } catch (err) {
      console.error('Failed to clear notifications:', err);
    }
  }, []);

  return {
    notifications: [...localNotifications, ...serverNotifications],
    pushLocal,
    markAllRead,
    clearAll,
  };
}
