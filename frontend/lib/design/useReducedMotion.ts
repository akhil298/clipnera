'use client';

import { useSyncExternalStore } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia(QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}

/**
 * True when the visitor asked the OS to minimise motion. Unlike
 * `hooks/usePrefersReducedMotion` (which starts `false` and corrects itself in
 * an effect), this is right on the first client render, so an overlay that
 * mounts already open never plays its entrance under reduced motion.
 * Proposed to replace that hook's body; see 02-design-system.md §8.
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}
