'use client';

import { AnimatePresence, motion } from 'framer-motion';
import type { ReactNode } from 'react';

import { motionPreset } from '@/lib/design/motion';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

/**
 * Sticky "Unsaved changes" bar (DS-L10, local until the Design System promotes it).
 * Sits above the phone tab bar (`bottom-16`) and at the bottom of the content on
 * wider screens. The message is a polite status so the change is announced once.
 */
export function SaveBar({ show, message, actions }: { show: boolean; message: ReactNode; actions: ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          role="region"
          aria-label="Unsaved changes"
          className="sticky bottom-16 z-cn-sticky mt-6 md:bottom-4"
          {...motionPreset('rise', reduced)}
        >
          <div className="flex flex-wrap items-center gap-3 rounded-cn-xl border border-cn-border-strong bg-cn-surface-raised px-4 py-3 shadow-cn-2">
            <span aria-hidden className="size-2 shrink-0 rounded-cn-full bg-cn-accent" />
            <p role="status" className="min-w-0 flex-1 text-cn-body font-medium text-cn-fg">
              {message}
            </p>
            <div className="flex flex-wrap items-center gap-2">{actions}</div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
