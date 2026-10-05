'use client';

import { AnimatePresence, motion, useIsPresent } from 'framer-motion';
import { X } from 'lucide-react';
import { type ReactNode, type RefObject, useRef } from 'react';

import { useReducedMotion } from '@/lib/design/useReducedMotion';
import { useFocusTrap, useScrollLock } from '@/lib/design/focus';
import { useLayer } from '@/lib/design/layers';
import { type MotionPresetName, motionPreset } from '@/lib/design/motion';
import { cx } from '@/lib/design/styles';

import { IconButton } from './IconButton';
import { Portal } from './Portal';

export interface ModalLayerProps {
  open: boolean;
  onClose: () => void;
  /** `alertdialog` for confirmations that need an answer; backdrop clicks do not close it. */
  role?: 'dialog' | 'alertdialog';
  labelledBy: string;
  describedBy?: string;
  /** Escape (and, for `dialog`, a backdrop click) closes. Default true. */
  dismissible?: boolean;
  initialFocusRef?: RefObject<HTMLElement | null>;
  /** Which z-index layer: drawers sit under dialogs. */
  layer: 'dialog' | 'drawer';
  /** Classes for the full-screen container that positions the panel. */
  placement: string;
  panelClassName: string;
  motion: MotionPresetName;
  children: ReactNode;
}

/**
 * The shared modal behaviour behind Dialog and Drawer: portal, scrim, focus
 * trap with focus return, Escape, scroll lock, enter and exit motion.
 */
export function ModalLayer(props: ModalLayerProps) {
  return (
    <Portal>
      <AnimatePresence>{props.open && <ModalContent {...props} />}</AnimatePresence>
    </Portal>
  );
}

function ModalContent({
  onClose,
  role = 'dialog',
  labelledBy,
  describedBy,
  dismissible = true,
  initialFocusRef,
  layer,
  placement,
  panelClassName,
  motion: preset,
  children,
}: ModalLayerProps) {
  // While the exit animation plays the panel is no longer "present": release focus at once.
  const present = useIsPresent();
  const panelRef = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const isTop = useLayer(present, dismissible ? onClose : undefined);
  useFocusTrap(panelRef, present, { isTop, initialFocusRef });
  useScrollLock(present);

  const scrim = motionPreset('fade', reduced);
  const panel = motionPreset(preset, reduced);
  const closeOnBackdrop = dismissible && role === 'dialog';

  return (
    <div className={cx('fixed inset-0 flex', layer === 'dialog' ? 'z-cn-dialog' : 'z-cn-drawer', placement)}>
      <motion.div
        aria-hidden
        className="absolute inset-0 bg-cn-overlay/60"
        {...scrim}
        onClick={closeOnBackdrop ? onClose : undefined}
      />
      <motion.div
        ref={panelRef}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        {...panel}
        className={cx(
          'relative flex flex-col border border-cn-border-strong bg-cn-surface-raised text-cn-fg shadow-cn-3 focus-visible:outline-none',
          panelClassName,
        )}
      >
        {children}
      </motion.div>
    </div>
  );
}

export interface ModalHeaderProps {
  titleId: string;
  descriptionId?: string;
  title: ReactNode;
  description?: ReactNode;
  onClose?: () => void;
}

/** Title, optional description and the close button, shared by Dialog and Drawer. */
export function ModalHeader({ titleId, descriptionId, title, description, onClose }: ModalHeaderProps) {
  return (
    <div className="flex items-start gap-3 px-5 pb-3 pt-5">
      <div className="min-w-0 flex-1 space-y-1">
        <h2 id={titleId} className="text-cn-title-sm font-semibold text-cn-fg">
          {title}
        </h2>
        {description && (
          <p id={descriptionId} className="text-cn-body text-cn-fg-secondary">
            {description}
          </p>
        )}
      </div>
      {onClose && <IconButton label="Close" icon={<X />} size="sm" tooltip={false} onClick={onClose} className="-mr-1.5 -mt-1" />}
    </div>
  );
}

/** Action row. Primary button last; on phones the buttons stack with the primary on top. */
export function ModalFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cx(
        'flex flex-col-reverse gap-2 border-t border-cn-border px-5 pt-4 sm:flex-row sm:items-center sm:justify-end',
        'pb-[max(1rem,env(safe-area-inset-bottom))]',
        '[&>button]:w-full sm:[&>button]:w-auto',
        className,
      )}
    >
      {children}
    </div>
  );
}
