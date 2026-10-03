'use client';

import { AnimatePresence, motion } from 'framer-motion';
import {
  cloneElement,
  type ReactElement,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';

import { useReducedMotion } from '@/lib/design/useReducedMotion';
import { useLayer } from '@/lib/design/layers';
import { motionPreset } from '@/lib/design/motion';
import { cx } from '@/lib/design/styles';
import { delay } from '@/lib/design/tokens';
import { type Side, useAnchoredPosition } from '@/lib/design/useAnchoredPosition';

import { Portal } from './Portal';

/** When the last tooltip closed; a second one within `tooltipSkip` opens without delay. */
let lastClosedAt = 0;
const HIDE_GRACE_MS = 100;

export interface TooltipProps {
  content: ReactNode;
  /** One focusable element. It receives `aria-describedby` (or `aria-labelledby` with `asLabel`). */
  children: ReactElement<{ 'aria-describedby'?: string; 'aria-labelledby'?: string }>;
  side?: Side;
  /** Use the tooltip as the trigger's name (icon-only buttons that have no other label). */
  asLabel?: boolean;
  disabled?: boolean;
}

/**
 * Supplementary text on hover and keyboard focus. Meets WCAG 1.4.13: Escape
 * dismisses it, the pointer can move onto it, and it stays until the pointer
 * or focus leaves. Never put essential information or controls in a tooltip.
 */
export function Tooltip({ content, children, side = 'top', asLabel = false, disabled = false }: TooltipProps) {
  const id = useId();
  const anchorRef = useRef<HTMLSpanElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [open, setOpen] = useState(false);
  const reduced = useReducedMotion();
  const { style } = useAnchoredPosition(open, anchorRef, panelRef, { side, align: 'center', offset: 6 });

  const clear = () => clearTimeout(timer.current);
  const show = (immediate: boolean) => {
    if (disabled) return;
    clear();
    const wait = immediate || Date.now() - lastClosedAt < delay.tooltipSkip ? 0 : delay.tooltip;
    timer.current = setTimeout(() => setOpen(true), wait);
  };
  const hide = useCallback((immediate = false) => {
    clear();
    const close = () => {
      setOpen((wasOpen) => {
        if (wasOpen) lastClosedAt = Date.now();
        return false;
      });
    };
    if (immediate) close();
    else timer.current = setTimeout(close, HIDE_GRACE_MS);
  }, []);

  useEffect(() => clear, []);
  useLayer(open, () => hide(true));

  const preset = motionPreset('fade', reduced);
  const relation = asLabel ? { 'aria-labelledby': id } : { 'aria-describedby': id };

  return (
    <>
      <span
        ref={anchorRef}
        className="inline-flex"
        onPointerEnter={(event) => event.pointerType !== 'touch' && show(false)}
        onPointerLeave={() => hide()}
        onFocus={() => show(true)}
        onBlur={() => hide(true)}
      >
        {cloneElement(children, relation)}
      </span>
      {/* Screen readers read this hidden copy, so the reference resolves whether or not the bubble is open. */}
      <span id={id} hidden>
        {content}
      </span>
      <Portal>
        <AnimatePresence>
          {open && (
            <motion.div
              ref={panelRef}
              aria-hidden
              style={style}
              onPointerEnter={clear}
              onPointerLeave={() => hide()}
              {...preset}
              className={cx(
                'z-cn-tooltip max-w-xs rounded-cn-sm border border-cn-border-strong bg-cn-surface-raised px-2 py-1',
                'text-cn-caption font-medium text-cn-fg shadow-cn-2',
              )}
            >
              {content}
            </motion.div>
          )}
        </AnimatePresence>
      </Portal>
    </>
  );
}
