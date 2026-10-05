'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { type FocusEvent, type ReactNode, type RefObject, useEffect, useId, useRef } from 'react';

import { useReducedMotion } from '@/lib/design/useReducedMotion';
import { focusFirst } from '@/lib/design/focus';
import { useDismissOnOutsidePointer, useLayer } from '@/lib/design/layers';
import { motionPreset } from '@/lib/design/motion';
import { cx, floatingSurface } from '@/lib/design/styles';
import { type Align, type Side, useAnchoredPosition } from '@/lib/design/useAnchoredPosition';
import { useControllableState } from '@/lib/design/useControllableState';

import { Portal } from './Portal';

export interface PopoverTriggerProps {
  ref: RefObject<HTMLButtonElement | null>;
  'aria-haspopup': 'dialog';
  'aria-expanded': boolean;
  'aria-controls': string | undefined;
  onClick: () => void;
}

export interface PopoverProps {
  /** Render the trigger and spread these props onto a button. */
  trigger: (props: PopoverTriggerProps) => ReactNode;
  /** Content, or a function that receives `close`. */
  children: ReactNode | ((close: () => void) => ReactNode);
  /** Visible heading; also the popover's accessible name. */
  title?: ReactNode;
  /** Accessible name when there is no visible title. */
  label?: string;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  side?: Side;
  align?: Align;
  className?: string;
}

/**
 * A small non-modal panel attached to a trigger: credits breakdown, filters,
 * a colour picker. Focus moves in on open; Escape, an outside click or
 * tabbing away closes it. For a list of actions use Menu.
 */
export function Popover({
  trigger,
  children,
  title,
  label,
  open,
  defaultOpen = false,
  onOpenChange,
  side = 'bottom',
  align = 'start',
  className,
}: PopoverProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [isOpen, setOpen] = useControllableState(open, defaultOpen, onOpenChange);
  const reduced = useReducedMotion();
  const { style, ready } = useAnchoredPosition(isOpen, triggerRef, panelRef, { side, align, offset: 8 });

  const close = () => setOpen(false);
  const closeAndReturn = () => {
    close();
    triggerRef.current?.focus();
  };

  useLayer(isOpen, closeAndReturn);
  useDismissOnOutsidePointer(isOpen, [triggerRef, panelRef], close);

  useEffect(() => {
    if (isOpen && ready && panelRef.current) focusFirst(panelRef.current);
  }, [isOpen, ready]);

  const onBlur = (event: FocusEvent<HTMLDivElement>) => {
    const next = event.relatedTarget as Node | null;
    if (next && !panelRef.current?.contains(next) && !triggerRef.current?.contains(next)) close();
  };

  const preset = motionPreset('rise', reduced);

  return (
    <>
      {trigger({
        ref: triggerRef,
        'aria-haspopup': 'dialog',
        'aria-expanded': isOpen,
        'aria-controls': isOpen ? id : undefined,
        onClick: () => setOpen(!isOpen),
      })}
      <Portal>
        <AnimatePresence>
          {isOpen && (
            <motion.div
              ref={panelRef}
              id={id}
              role="dialog"
              aria-labelledby={title ? titleId : undefined}
              aria-label={title ? undefined : label}
              tabIndex={-1}
              style={style}
              onBlur={onBlur}
              {...preset}
              className={cx('z-cn-popover w-72 max-w-[calc(100vw-16px)] p-4 focus-visible:outline-none', floatingSurface, className)}
            >
              {title && (
                <h2 id={titleId} className="mb-2 text-cn-body font-semibold text-cn-fg">
                  {title}
                </h2>
              )}
              {typeof children === 'function' ? children(closeAndReturn) : children}
            </motion.div>
          )}
        </AnimatePresence>
      </Portal>
    </>
  );
}
