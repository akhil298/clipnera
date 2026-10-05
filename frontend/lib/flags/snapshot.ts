import { getToken } from '@/lib/auth';

import type { FlagsBootstrapResponse } from './types';

/** Last bootstrap per subject, so a returning user starts from their flags instead of defaults (06-flags §4.3). */
const KEY_PREFIX = 'flags:v1:';
const MAX_AGE_MS = 24 * 3600 * 1000;

interface StoredSnapshot {
  savedAt: number;
  payload: FlagsBootstrapResponse;
}

/** The signed-in user's id from the token's `sub`, or 'anonymous'. Browser only. */
export function flagSubject(): string {
  const token = getToken();
  if (!token) return 'anonymous';
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const sub = (JSON.parse(atob(payload)) as { sub?: unknown }).sub;
    return typeof sub === 'string' && sub ? sub : 'anonymous';
  } catch {
    return 'anonymous';
  }
}

export function readSnapshot(subject: string): FlagsBootstrapResponse | undefined {
  try {
    const raw = localStorage.getItem(KEY_PREFIX + subject);
    if (!raw) return undefined;
    const stored = JSON.parse(raw) as StoredSnapshot;
    return Date.now() - stored.savedAt < MAX_AGE_MS ? stored.payload : undefined;
  } catch {
    return undefined;
  }
}

export function writeSnapshot(subject: string, payload: FlagsBootstrapResponse): void {
  try {
    const stored: StoredSnapshot = { savedAt: Date.now(), payload };
    localStorage.setItem(KEY_PREFIX + subject, JSON.stringify(stored));
  } catch {
    // Storage full or blocked: the next visit starts from defaults, which is safe.
  }
}
