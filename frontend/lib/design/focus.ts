'use client';

import { type RefObject, useEffect } from 'react';

const TABBABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'iframe',
  'audio[controls]',
  'video[controls]',
  '[contenteditable]:not([contenteditable="false"])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/** Elements Tab can reach inside `root`, in document order, skipping hidden ones. */
export function getTabbables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(TABBABLE)).filter(
    (el) => el.tabIndex >= 0 && el.getClientRects().length > 0 && !el.closest('[inert],[aria-hidden="true"]'),
  );
}

/** Focus the element marked `data-autofocus`, else the first tabbable, else the container. */
export function focusFirst(root: HTMLElement): void {
  const target = root.querySelector<HTMLElement>('[data-autofocus]') ?? getTabbables(root)[0] ?? root;
  target.focus({ preventScroll: true });
}

interface FocusTrapOptions {
  /** Whether this trap is the newest open layer (from `useLayer`). */
  isTop: () => boolean;
  /** Element to focus on open; defaults to `data-autofocus`, then the first tabbable. */
  initialFocusRef?: RefObject<HTMLElement | null>;
  /** Return focus to the element that had it before opening. Default true. */
  restoreFocus?: boolean;
}

/**
 * Keeps keyboard focus inside `containerRef` while `active`: moves focus in on
 * open, wraps Tab and Shift+Tab, pulls stray focus back, and returns focus to
 * the trigger on close. Yields to any newer layer (a menu opened inside).
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean,
  { isTop, initialFocusRef, restoreFocus = true }: FocusTrapOptions,
): void {
  useEffect(() => {
    const container = containerRef.current;
    if (!active || !container) return;
    const previous = document.activeElement as HTMLElement | null;

    if (initialFocusRef?.current) initialFocusRef.current.focus({ preventScroll: true });
    else focusFirst(container);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !isTop()) return;
      const tabbables = getTabbables(container);
      if (tabbables.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }
      const first = tabbables[0];
      const last = tabbables[tabbables.length - 1];
      const current = document.activeElement;
      if (event.shiftKey && (current === first || !container.contains(current))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (current === last || !container.contains(current))) {
        event.preventDefault();
        first.focus();
      }
    };
    const onFocusIn = (event: FocusEvent) => {
      if (isTop() && !container.contains(event.target as Node)) focusFirst(container);
    };

    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('focusin', onFocusIn);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('focusin', onFocusIn);
      if (restoreFocus && previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [active, containerRef, initialFocusRef, isTop, restoreFocus]);
}

let scrollLocks = 0;
let savedBodyStyle: { overflow: string; paddingRight: string } | null = null;

/** Stops the page behind a modal from scrolling, without a layout jump. Nests safely. */
export function useScrollLock(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const { body, documentElement } = document;
    if (scrollLocks === 0) {
      savedBodyStyle = { overflow: body.style.overflow, paddingRight: body.style.paddingRight };
      const scrollbar = window.innerWidth - documentElement.clientWidth;
      body.style.overflow = 'hidden';
      if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;
    }
    scrollLocks += 1;
    return () => {
      scrollLocks -= 1;
      if (scrollLocks === 0 && savedBodyStyle) {
        body.style.overflow = savedBodyStyle.overflow;
        body.style.paddingRight = savedBodyStyle.paddingRight;
        savedBodyStyle = null;
      }
    };
  }, [active]);
}
