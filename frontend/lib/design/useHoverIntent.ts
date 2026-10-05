'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { delay as delays } from './tokens';
import { useReducedMotion } from './useReducedMotion';

export interface HoverIntentHandlers {
  onPointerEnter: () => void;
  onPointerLeave: () => void;
  onFocus: () => void;
  onBlur: () => void;
}

/**
 * True after the pointer has rested on (or keyboard focus has reached) an
 * element for `delayMs`, false as soon as it leaves. Never true under reduced
 * motion, so media hover previews fall back to the poster (02 §5.4).
 */
export function useHoverIntent(delayMs: number = delays.mediaHover, enabled = true): { active: boolean; handlers: HoverIntentHandlers } {
  const reduced = useReducedMotion();
  const [active, setActive] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const begin = useCallback(() => {
    if (reduced || !enabled) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setActive(true), delayMs);
  }, [delayMs, enabled, reduced]);

  const end = useCallback(() => {
    clearTimeout(timer.current);
    setActive(false);
  }, []);

  useEffect(() => () => clearTimeout(timer.current), []);

  return { active, handlers: { onPointerEnter: begin, onPointerLeave: end, onFocus: begin, onBlur: end } };
}
