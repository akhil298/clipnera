"use client";
import React from 'react';
import {
  X,
  Bell,
  CheckCircle2,
  CalendarDays,
  Flame,
  Zap,
  Check,
  Trash2
} from 'lucide-react';
import { AppNotification } from '@/lib/types';

interface NotificationsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  notifications: AppNotification[];
  onMarkAllRead: () => void;
  onClearAll: () => void;
}

export const NotificationsDrawer: React.FC<NotificationsDrawerProps> = ({
  isOpen,
  onClose,
  notifications,
  onMarkAllRead,
  onClearAll,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-md h-full bg-neutral-900 border-l border-neutral-800 p-6 flex flex-col justify-between shadow-2xl space-y-4 animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-neutral-800">
          <div className="flex items-center gap-2">
            <Bell className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Activity & Alerts
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-neutral-400 hover:text-white rounded-lg hover:bg-neutral-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Notifications List */}
        <div className="flex-1 overflow-y-auto space-y-3 pr-1">
          {notifications.length === 0 ? (
            <div className="text-center py-12 text-neutral-500 text-xs">
              No new notifications. Everything is up to date!
            </div>
          ) : (
            notifications.map((notif) => (
              <div
                key={notif.id}
                className={`p-3.5 rounded-2xl border transition-all space-y-1.5 ${
                  notif.read
                    ? 'bg-neutral-950/60 border-neutral-800/80 text-neutral-400'
                    : 'bg-neutral-950 border-amber-500/30 text-white shadow-md'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {notif.type === 'render_complete' && (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    {notif.type === 'scheduled_post' && (
                      <CalendarDays className="w-3.5 h-3.5 text-sky-400" />
                    )}
                    {notif.type === 'virality_alert' && (
                      <Flame className="w-3.5 h-3.5 text-amber-400" />
                    )}
                    {notif.type === 'credit_update' && (
                      <Zap className="w-3.5 h-3.5 text-violet-400" />
                    )}
                    <h4 className="text-xs font-bold text-white">{notif.title}</h4>
                  </div>
                  <span className="text-[10px] font-mono text-neutral-500">
                    {notif.timestamp}
                  </span>
                </div>

                <p className="text-[11px] text-neutral-300 leading-snug">
                  {notif.message}
                </p>
              </div>
            ))
          )}
        </div>

        {/* Footer Actions */}
        <div className="pt-4 border-t border-neutral-800 flex items-center justify-between gap-2">
          <button
            onClick={onMarkAllRead}
            className="text-xs text-neutral-400 hover:text-white font-semibold flex items-center gap-1.5"
          >
            <Check className="w-3.5 h-3.5" />
            <span>Mark All as Read</span>
          </button>

          <button
            onClick={onClearAll}
            className="text-xs text-neutral-500 hover:text-rose-400 font-semibold flex items-center gap-1.5"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear History</span>
          </button>
        </div>
      </div>
    </div>
  );
};
