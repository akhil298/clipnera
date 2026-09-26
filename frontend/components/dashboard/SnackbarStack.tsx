"use client";
import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { AppNotification } from '@/lib/types';

const AUTO_DISMISS_MS = 6000;

interface SnackbarStackProps {
  items: AppNotification[];
  onDismiss: (id: string) => void;
  /** Opens the project a notification is about. */
  onView: (notification: AppNotification) => void;
}

const Snackbar: React.FC<{
  item: AppNotification;
  onDismiss: (id: string) => void;
  onView: (notification: AppNotification) => void;
}> = ({ item, onDismiss, onView }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [isTabVisible, setIsTabVisible] = useState(() => document.visibilityState === 'visible');
  const remainingMs = useRef(AUTO_DISMISS_MS);

  useEffect(() => {
    const onVisibilityChange = () => setIsTabVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, []);

  // Counts down only while the tab is visible and the pointer is off the toast,
  // so one that lands while the user is on another tab waits for them.
  useEffect(() => {
    if (!isTabVisible || isHovered) return;
    const startedAt = Date.now();
    const timeoutId = setTimeout(() => onDismiss(item.id), remainingMs.current);
    return () => {
      clearTimeout(timeoutId);
      remainingMs.current -= Date.now() - startedAt;
    };
  }, [isTabVisible, isHovered, item.id, onDismiss]);

  const failed = item.type === 'render_failed';

  return (
    <div
      role="status"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`pointer-events-auto w-full sm:w-96 p-3.5 rounded-2xl bg-neutral-900 border shadow-2xl flex items-start gap-3 animate-in slide-in-from-bottom-4 fade-in duration-300 ${
        failed ? 'border-rose-500/40' : 'border-emerald-500/40'
      }`}
    >
      {failed ? (
        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-rose-400" />
      ) : (
        <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-emerald-400" />
      )}
      <div className="flex-1 min-w-0 space-y-1">
        <h4 className="text-xs font-bold text-white">{item.title}</h4>
        <p className="text-[11px] text-neutral-300 leading-snug">{item.message}</p>
        {item.projectId && (
          <button
            onClick={() => {
              onView(item);
              onDismiss(item.id);
            }}
            className="text-[11px] font-semibold text-amber-400 hover:text-amber-300"
          >
            View project
          </button>
        )}
      </div>
      <button
        onClick={() => onDismiss(item.id)}
        aria-label="Dismiss notification"
        className="p-1 text-neutral-500 hover:text-white rounded-lg hover:bg-neutral-800 transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};

export const SnackbarStack: React.FC<SnackbarStackProps> = ({ items, onDismiss, onView }) => {
  if (items.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 inset-x-4 sm:left-auto sm:right-6 sm:bottom-6 z-[60] flex flex-col items-end gap-2"
    >
      {items.map((item) => (
        <Snackbar key={item.id} item={item} onDismiss={onDismiss} onView={onView} />
      ))}
    </div>
  );
};
