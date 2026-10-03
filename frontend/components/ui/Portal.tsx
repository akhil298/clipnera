'use client';

import { type ReactNode, useSyncExternalStore } from 'react';
import { createPortal } from 'react-dom';

const subscribe = () => () => {};

/** False during server render and hydration, true after. */
export function useIsClient(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}

/** Renders overlays on `document.body` so no ancestor's overflow or stacking context clips them. */
export function Portal({ children }: { children: ReactNode }) {
  return useIsClient() ? createPortal(children, document.body) : null;
}
