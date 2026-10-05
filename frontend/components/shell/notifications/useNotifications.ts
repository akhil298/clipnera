'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { type ToastTone, useToast } from '@/components/ui';
import {
  clearNotifications,
  type InAppNotification,
  type InAppNotificationList,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/lib/api/notifications';
import { accountKeys } from '@/lib/query/keys/account';
import { creditKeys } from '@/lib/query/keys/credits';
import { notificationKeys } from '@/lib/query/keys/notifications';

import { isFailure, notificationHref } from './notificationMeta';

const MINUTE = 60_000;
/** Undo stays possible this long; the toast itself shows for 6 s (screens/01 §5.2, API-10's 10 s window). */
const CLEAR_COMMIT_MS = 10_000;
const INBOX_KEY = notificationKeys.inbox();

const toneOf = (item: InAppNotification): ToastTone =>
  isFailure(item) ? 'danger' : item.kind === 'social_expiring' || item.kind === 'social_expired' ? 'info' : item.kind === 'payment_approved' ? 'neutral' : 'success';

/** Shows a system notification for arrivals while the tab is hidden, once the user turned them on. */
function notifyBrowser(item: InAppNotification) {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted' || document.visibilityState === 'visible') return;
  new Notification(item.title, { body: item.message, tag: item.id });
}

/**
 * The inbox (screens/01 §5.2). Polls every minute and on focus until the event
 * stream lands; each new unread item after the first load becomes a toast (and a
 * browser notification when the tab is hidden). Clear all hides the list at once
 * and deletes on the server only after the Undo window, because the backend
 * delete is final.
 */
export function useNotifications() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const router = useRouter();

  const inbox = useQuery({
    queryKey: INBOX_KEY,
    queryFn: ({ signal }) => listNotifications(signal),
    staleTime: MINUTE,
    gcTime: 30 * MINUTE,
    refetchInterval: MINUTE,
  });

  const [clearing, setClearing] = useState<ReadonlySet<string>>(() => new Set());
  const items = useMemo(() => (inbox.data?.notifications ?? []).filter((item) => !clearing.has(item.id)), [inbox.data, clearing]);
  const unread = items.filter((item) => item.read_at === null).length;

  /** Optimistically applies `change` to the cached inbox; returns the previous value for rollback. */
  const patch = useCallback(
    (change: (item: InAppNotification) => InAppNotification) => {
      const previous = queryClient.getQueryData<InAppNotificationList>(INBOX_KEY);
      if (previous) queryClient.setQueryData<InAppNotificationList>(INBOX_KEY, { notifications: previous.notifications.map(change) });
      return previous;
    },
    [queryClient],
  );

  const restore = (previous: InAppNotificationList | undefined) => previous && queryClient.setQueryData(INBOX_KEY, previous);

  const { mutate: readOne } = useMutation({
    mutationFn: markNotificationRead,
    onMutate: async (id: string) => {
      await queryClient.cancelQueries({ queryKey: INBOX_KEY });
      const readAt = new Date().toISOString();
      return patch((item) => (item.id === id && item.read_at === null ? { ...item, read_at: readAt } : item));
    },
    onError: (_error, _id, previous) => restore(previous),
    onSettled: () => queryClient.invalidateQueries({ queryKey: INBOX_KEY }),
  });

  const readAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: INBOX_KEY });
      const readAt = new Date().toISOString();
      return patch((item) => (item.read_at === null ? { ...item, read_at: readAt } : item));
    },
    onSuccess: (data) => queryClient.setQueryData(INBOX_KEY, data),
    onError: (_error, _vars, previous) => {
      restore(previous);
      toast.show({ title: 'I couldn’t mark them read', description: 'Nothing changed. Try again.', tone: 'danger', duration: 6000 });
    },
  });

  const commitTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (commitTimer.current) clearTimeout(commitTimer.current);
  }, []);

  const clearAll = useCallback(() => {
    const ids = new Set(items.map((item) => item.id));
    if (ids.size === 0) return;
    setClearing(ids);
    let committed = false;

    commitTimer.current = setTimeout(async () => {
      committed = true;
      try {
        queryClient.setQueryData(INBOX_KEY, await clearNotifications());
        setClearing(new Set());
      } catch {
        setClearing(new Set());
        toast.show({ title: 'I couldn’t clear notifications', description: 'They are all still here. Try again.', tone: 'danger', duration: 6000 });
      }
    }, CLEAR_COMMIT_MS);

    toast.show({
      title: `Cleared ${ids.size} ${ids.size === 1 ? 'notification' : 'notifications'}`,
      duration: 6000,
      action: {
        label: 'Undo',
        onClick: () => {
          if (committed) {
            toast.show({ title: 'Already cleared', description: 'Those notifications were removed for good.' });
            return;
          }
          if (commitTimer.current) clearTimeout(commitTimer.current);
          setClearing(new Set());
        },
      },
    });
  }, [items, queryClient, toast]);

  const open = useCallback(
    (item: InAppNotification) => {
      if (item.read_at === null) readOne(item.id);
    },
    [readOne],
  );

  // Arrivals after the first load: toast, browser notification, and refresh what they report.
  const seen = useRef<Set<string> | null>(null);
  useEffect(() => {
    const list = inbox.data?.notifications;
    if (!list) return;
    if (!seen.current) {
      seen.current = new Set(list.map((item) => item.id));
      return;
    }
    const fresh = list.filter((item) => item.read_at === null && !seen.current!.has(item.id)).reverse();
    list.forEach((item) => seen.current!.add(item.id));
    for (const item of fresh) {
      const href = notificationHref(item);
      toast.show({
        title: item.title,
        description: item.message,
        tone: toneOf(item),
        action: href
          ? {
              label: 'Open',
              onClick: () => {
                open(item);
                router.push(href);
              },
            }
          : undefined,
      });
      notifyBrowser(item);
      if (item.kind === 'payment_approved') {
        void queryClient.invalidateQueries({ queryKey: creditKeys.all });
        void queryClient.invalidateQueries({ queryKey: accountKeys.me() });
      }
    }
  }, [inbox.data, toast, router, open, queryClient]);

  return {
    items,
    unread,
    /** First load still running (no list yet). */
    loading: inbox.isPending,
    /** The last refresh failed; `items` still holds the last list if there was one. */
    error: inbox.isError,
    retry: () => inbox.refetch(),
    open,
    markAllRead: () => readAll.mutate(),
    markingAll: readAll.isPending,
    clearAll,
  };
}
