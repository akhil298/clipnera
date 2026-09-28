"use client";
import React, { useEffect } from 'react';
import { X, Bell, CheckCircle2, AlertTriangle, CalendarDays, Flame, Zap, Check, Trash2, ChevronRight } from 'lucide-react';
import { AppNotification } from '@/lib/types';

interface NotificationsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  notifications: AppNotification[];
  onMarkAllRead: () => void;
  onClearAll: () => void;
  /** Opens the project a notification is about. */
  onView?: (notification: AppNotification) => void;
}

const KIND_STYLES: Record<AppNotification['type'], { icon: React.FC<{ className?: string }>; tint: string }> = {
  render_complete: { icon: CheckCircle2, tint: 'bg-emerald-500/10 text-emerald-400' },
  render_failed: { icon: AlertTriangle, tint: 'bg-rose-500/10 text-rose-400' },
  scheduled_post: { icon: CalendarDays, tint: 'bg-sky-500/10 text-sky-400' },
  virality_alert: { icon: Flame, tint: 'bg-amber-500/10 text-amber-400' },
  credit_update: { icon: Zap, tint: 'bg-violet-500/10 text-violet-400' },
};

/**
 * Notifications: a popover under the bell on larger screens and a bottom
 * sheet on phones, so a quick glance doesn't take over the whole page.
 */
export const NotificationsDrawer: React.FC<NotificationsDrawerProps> = ({
  isOpen,
  onClose,
  notifications,
  onMarkAllRead,
  onClearAll,
  onView,
}) => {
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const unread = notifications.filter((n) => !n.read).length;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 md:bg-black/20 backdrop-blur-[2px] animate-in fade-in duration-150"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-label="Notifications"
        className="absolute inset-x-0 bottom-0 max-h-[80dvh] rounded-t-2xl md:inset-x-auto md:bottom-auto md:right-4 md:top-[4.5rem] md:w-[400px] md:max-h-[70vh] md:rounded-2xl bg-neutral-900 border border-neutral-800 shadow-2xl shadow-black/60 flex flex-col animate-in slide-in-from-bottom md:slide-in-from-top-2 duration-200"
      >
        <div className="md:hidden mx-auto mt-2 h-1 w-10 rounded-full bg-neutral-700" aria-hidden="true" />
        <div className="flex items-center gap-2 px-4 py-3 border-b border-neutral-800">
          <Bell className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-bold text-white">Notifications</h3>
          {unread > 0 && (
            <span className="h-5 px-1.5 rounded-full bg-amber-500/15 text-amber-300 text-[11px] font-bold flex items-center">
              {unread} new
            </span>
          )}
          <span className="flex-1" />
          <button
            type="button"
            onClick={onMarkAllRead}
            disabled={unread === 0}
            className="text-xs font-semibold text-neutral-400 hover:text-white disabled:opacity-40 disabled:hover:text-neutral-400 flex items-center gap-1"
          >
            <Check className="w-3.5 h-3.5" />
            Mark all read
          </button>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-neutral-400 hover:text-white rounded-lg hover:bg-neutral-800 transition-colors"
            aria-label="Close notifications"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2">
          {notifications.length === 0 ? (
            <div className="text-center py-12 px-6">
              <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-neutral-800 flex items-center justify-center">
                <Bell className="w-4 h-4 text-neutral-500" />
              </div>
              <p className="text-sm font-semibold text-neutral-300">You’re all caught up</p>
              <p className="text-xs text-neutral-500 mt-1">We’ll let you know when clips are ready or a post goes out.</p>
            </div>
          ) : (
            notifications.map((notif) => {
              const kind = KIND_STYLES[notif.type] ?? KIND_STYLES.render_complete;
              const Icon = kind.icon;
              const canOpen = Boolean(onView && notif.projectId);
              return (
                <button
                  key={notif.id}
                  type="button"
                  disabled={!canOpen}
                  onClick={() => {
                    if (!canOpen) return;
                    onView?.(notif);
                    onClose();
                  }}
                  className={`w-full flex items-start gap-3 p-2.5 rounded-xl text-left transition-colors ${
                    canOpen ? 'hover:bg-neutral-800/70' : 'cursor-default'
                  }`}
                >
                  <span className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${kind.tint}`}>
                    <Icon className="w-4 h-4" />
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="flex items-center gap-2">
                      <span className={`text-[13px] font-semibold truncate ${notif.read ? 'text-neutral-300' : 'text-white'}`}>
                        {notif.title}
                      </span>
                      {!notif.read && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" aria-label="Unread" />}
                    </span>
                    <span className="block text-xs text-neutral-400 leading-snug mt-0.5">{notif.message}</span>
                    <span className="block text-[11px] text-neutral-500 mt-1">{notif.timestamp}</span>
                  </span>
                  {canOpen && <ChevronRight className="w-4 h-4 text-neutral-600 mt-2 shrink-0" />}
                </button>
              );
            })
          )}
        </div>

        {notifications.length > 0 && (
          <div className="px-4 py-2.5 border-t border-neutral-800 pb-[max(0.625rem,env(safe-area-inset-bottom))]">
            <button
              type="button"
              onClick={onClearAll}
              className="w-full h-9 rounded-lg text-xs text-neutral-400 hover:text-rose-300 hover:bg-rose-500/5 font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Clear all
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
