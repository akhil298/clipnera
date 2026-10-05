'use client';

import { useSyncExternalStore } from 'react';

import { isAuthenticated } from '@/lib/auth';

function subscribe(onChange: () => void): () => void {
  window.addEventListener('storage', onChange);
  return () => window.removeEventListener('storage', onChange);
}

/**
 * Whether this browser holds a live session. The token lives in localStorage,
 * so the server render (and hydration) assume signed out, then correct.
 */
export function useSignedIn(): boolean {
  return useSyncExternalStore(subscribe, isAuthenticated, () => false);
}
