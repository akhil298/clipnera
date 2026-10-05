import { apiFetch } from './client';

/**
 * The in-app inbox. Types mirror backend/notifications/schema.py
 * (InAppNotificationResponse, InAppNotificationListResponse) and
 * backend/notifications/model.py (NotificationKind); keep them in step.
 */

/** backend/notifications/model.py NotificationKind. */
export type NotificationKind =
  | 'pipeline_completed'
  | 'pipeline_failed'
  | 'payment_approved'
  | 'reel_ready'
  | 'reel_failed'
  | 'social_expiring'
  | 'social_expired';

/** InAppNotificationResponse. Timestamps are naive UTC ISO strings (parse with `parseApiDate`). */
export interface InAppNotification {
  id: string;
  kind: NotificationKind;
  title: string;
  message: string;
  project_id: string | null;
  read_at: string | null;
  created_at: string;
}

/** InAppNotificationListResponse. */
export interface InAppNotificationList {
  notifications: InAppNotification[];
}

/** Newest first; the backend caps `limit` at 100. */
export const listNotifications = (signal?: AbortSignal, limit = 30) =>
  apiFetch<InAppNotificationList>('/notifications', { query: { limit }, signal });

/** Returns the inbox with every item read. */
export const markAllNotificationsRead = () => apiFetch<InAppNotificationList>('/notifications/read-all', { method: 'POST' });

/** Deletes every notification for good; returns the (empty) inbox. Undo is handled before this is sent. */
export const clearNotifications = () => apiFetch<InAppNotificationList>('/notifications', { method: 'DELETE' });

/**
 * Marks one notification read when its row is opened (screens/01 §5.2).
 * NEEDS-BACKEND: POST /notifications/{id}/read returning InAppNotificationResponse.
 * Until it exists this fails with a normal ApiError and the row turns unread again.
 */
export const markNotificationRead = (id: string) =>
  apiFetch<InAppNotification>(`/notifications/${encodeURIComponent(id)}/read`, { method: 'POST' });
