'use client';

import { type RefObject, useLayoutEffect } from 'react';

/**
 * Grows a textarea with its content up to `maxRows`, then scrolls.
 * Re-measures whenever `value` changes.
 */
export function useAutosize(ref: RefObject<HTMLTextAreaElement | null>, value: string, minRows: number, maxRows: number): void {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const style = window.getComputedStyle(el);
    const line = parseFloat(style.lineHeight) || 20;
    const chrome = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    el.style.height = 'auto';
    const height = Math.min(Math.max(el.scrollHeight, line * minRows + chrome), line * maxRows + chrome);
    el.style.height = `${height}px`;
    el.style.overflowY = el.scrollHeight > height ? 'auto' : 'hidden';
  }, [ref, value, minRows, maxRows]);
}
