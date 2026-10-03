'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { CircleAlert, CircleCheck, Info, X } from 'lucide-react';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { useReducedMotion } from '@/lib/design/useReducedMotion';
import { motionPreset } from '@/lib/design/motion';
import { cx, floatingSurface, focusRing } from '@/lib/design/styles';

import { IconButton } from './IconButton';
import { Portal } from './Portal';

export type ToastTone = 'neutral' | 'success' | 'danger' | 'info';

export interface ToastOptions {
  /** What happened, in a few words: "Export ready". */
  title: string;
  /** Optional detail. For errors: what is still safe. */
  description?: string;
  tone?: ToastTone;
  /** One action, e.g. "View project", "Try again", "Undo". */
  action?: { label: string; onClick: () => void };
  /** Milliseconds visible. `null` stays until dismissed. Default 6000; danger defaults to `null`. */
  duration?: number | null;
}

interface ToastRecord extends ToastOptions {
  id: string;
}

interface ToastApi {
  show: (toast: ToastOptions) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
const MAX_VISIBLE = 3;
const DEFAULT_DURATION = 6000;

/** `const toast = useToast(); toast.show({ title: 'Export ready', tone: 'success' })`. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error('useToast must be used inside <ToastProvider>');
  return api;
}

const ICON: Record<ToastTone, ReactNode> = {
  neutral: null,
  success: <CircleCheck className="text-cn-success-text" />,
  danger: <CircleAlert className="text-cn-danger-text" />,
  info: <Info className="text-cn-info-text" />,
};

/**
 * Hosts toasts for everything below it. Announcements go through two
 * persistent live regions (polite, and assertive for errors) so each toast is
 * read exactly once; the visible stack itself is not a live region.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const [announcement, setAnnouncement] = useState({ polite: '', assertive: '' });
  const nextId = useRef(0);

  const dismiss = useCallback((id: string) => setToasts((list) => list.filter((toast) => toast.id !== id)), []);

  const show = useCallback((toast: ToastOptions) => {
    nextId.current += 1;
    const id = `toast-${nextId.current}`;
    setToasts((list) => [...list, { ...toast, id }]);
    const text = [toast.title, toast.description].filter(Boolean).join('. ');
    const channel = toast.tone === 'danger' ? 'assertive' : 'polite';
    // Clear, then set on the next frame, so the same message twice is still read twice.
    setAnnouncement({ polite: '', assertive: '' });
    requestAnimationFrame(() => setAnnouncement((current) => ({ ...current, [channel]: text })));
    return id;
  }, []);

  const api = useMemo(() => ({ show, dismiss }), [show, dismiss]);
  const visible = toasts.slice(-MAX_VISIBLE);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="sr-only" role="status" aria-live="polite">
        {announcement.polite}
      </div>
      <div className="sr-only" role="alert" aria-live="assertive">
        {announcement.assertive}
      </div>
      <Portal>
        <section
          aria-label="Notifications"
          className="pointer-events-none fixed inset-x-4 bottom-4 z-cn-toast flex flex-col items-end gap-2 sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-96"
        >
          <AnimatePresence initial={false}>
            {visible.map((toast) => (
              <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
            ))}
          </AnimatePresence>
        </section>
      </Portal>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDismiss }: { toast: ToastRecord; onDismiss: (id: string) => void }) {
  const { id, title, description, tone = 'neutral', action } = toast;
  const duration = toast.duration === undefined ? (tone === 'danger' ? null : DEFAULT_DURATION) : toast.duration;
  const reduced = useReducedMotion();
  const [paused, setPaused] = useState(false);
  const [tabVisible, setTabVisible] = useState(true);
  const remaining = useRef(duration ?? 0);

  useEffect(() => {
    const onVisibility = () => setTabVisible(document.visibilityState === 'visible');
    onVisibility();
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  // Counts down only while visible, unhovered and unfocused (WCAG 2.2.1: the user controls timing).
  useEffect(() => {
    if (duration === null || paused || !tabVisible) return;
    const started = Date.now();
    const timer = setTimeout(() => onDismiss(id), remaining.current);
    return () => {
      clearTimeout(timer);
      remaining.current -= Date.now() - started;
    };
  }, [duration, paused, tabVisible, id, onDismiss]);

  const preset = motionPreset('rise', reduced);

  return (
    <motion.div
      layout={!reduced}
      {...preset}
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(event) => !event.currentTarget.contains(event.relatedTarget as Node | null) && setPaused(false)}
      className={cx('pointer-events-auto flex w-full items-start gap-3 p-3.5', floatingSurface)}
    >
      {ICON[tone] && (
        <span aria-hidden className="mt-0.5 inline-flex [&_svg]:size-4">
          {ICON[tone]}
        </span>
      )}
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-cn-body font-semibold text-cn-fg">{title}</p>
        {description && <p className="text-cn-label text-cn-fg-secondary">{description}</p>}
        {action && (
          <button
            type="button"
            onClick={() => {
              action.onClick();
              onDismiss(id);
            }}
            className={cx('mt-1.5 rounded-cn-xs text-cn-label font-semibold text-cn-accent-text hover:underline', focusRing)}
          >
            {action.label}
          </button>
        )}
      </div>
      <IconButton label="Dismiss" icon={<X />} size="sm" tooltip={false} onClick={() => onDismiss(id)} className="-mr-1.5 -mt-1.5" />
    </motion.div>
  );
}
