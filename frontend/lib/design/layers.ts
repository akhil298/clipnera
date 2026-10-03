'use client';

import { type RefObject, useCallback, useEffect, useId, useRef } from 'react';

/**
 * Open overlays, oldest first. Only the newest layer answers Escape and owns
 * focus, so a menu opened inside a dialog closes before the dialog does.
 */
const stack: string[] = [];

const isTopLayer = (id: string): boolean => stack[stack.length - 1] === id;

/** Registers an open overlay. Returns `isTop()` for focus management. */
export function useLayer(open: boolean, onEscape?: () => void): () => boolean {
  const id = useId();
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;

  useEffect(() => {
    if (!open) return;
    stack.push(id);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.isComposing || !isTopLayer(id) || !onEscapeRef.current) return;
      event.preventDefault();
      onEscapeRef.current();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      const index = stack.lastIndexOf(id);
      if (index >= 0) stack.splice(index, 1);
    };
  }, [open, id]);

  return useCallback(() => isTopLayer(id), [id]);
}

/** Closes a non-modal overlay when the pointer goes down outside it and its trigger. */
export function useDismissOnOutsidePointer(
  open: boolean,
  refs: ReadonlyArray<RefObject<HTMLElement | null>>,
  onDismiss: () => void,
): void {
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;
  const refsRef = useRef(refs);
  refsRef.current = refs;

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (refsRef.current.some((ref) => ref.current?.contains(target))) return;
      onDismissRef.current();
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);
}
