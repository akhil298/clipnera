import { safeNextPath } from '@/lib/routing/auth-rules';

/**
 * What the sign-in page keeps in the browser across the Google round trip
 * (screens/01 §3.1, §3.4). Storage can be refused (private windows, blocked
 * site data), so every access is guarded and a failure only loses the
 * convenience, never the sign-in.
 */

/** Written by the landing page, read once by Home (`components/home/handoff.ts`). Sign-in only peeks. */
const PENDING_PROMPT_KEY = 'cn.pendingPrompt';
/** Where to go after the callback lands on /dashboard. */
const NEXT_KEY = 'cn.signInNext';
/** Set when Google was started without the consent tick; cleared by any successful sign-in. */
const CONSENT_SKIPPED_KEY = 'cn.consentSkipped';
/** Hides the consent box on a device that has signed in before (§3.1). */
const SIGNED_IN_BEFORE_KEY = 'cn_signed_in_before';

/** Matches the state's lifetime in the callback: an older `next` belongs to an abandoned attempt. */
const NEXT_MAX_AGE_MS = 10 * 60_000;

function read(storage: () => Storage, key: string): string | null {
  try {
    return storage().getItem(key);
  } catch {
    return null;
  }
}

function write(storage: () => Storage, key: string, value: string | null): void {
  try {
    if (value === null) storage().removeItem(key);
    else storage().setItem(key, value);
  } catch {
    // Refused storage: the step it supports is simply skipped.
  }
}

const session = () => window.sessionStorage;
const local = () => window.localStorage;

export interface PromptPreview {
  text: string;
  url: string | null;
}

/** The landing page's kept prompt, without consuming it: Home reads and clears it after sign-in. */
export function peekPendingPrompt(): PromptPreview | null {
  const raw = read(session, PENDING_PROMPT_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as { text?: unknown; url?: unknown };
    const text = typeof parsed.text === 'string' ? parsed.text.trim() : '';
    const url = typeof parsed.url === 'string' && parsed.url ? parsed.url : null;
    return text || url ? { text, url } : null;
  } catch {
    return null;
  }
}

export const hasPendingPrompt = (): boolean => peekPendingPrompt() !== null;

/** Saved just before leaving for Google; ignored unless it is a safe same-origin path. */
export function rememberSignInNext(next: string | null): void {
  const safe = safeNextPath(next);
  write(session, NEXT_KEY, safe ? JSON.stringify({ path: safe, at: Date.now() }) : null);
}

/** The saved `next`, once. Null when none, stale, or unsafe. */
export function takeSignInNext(): string | null {
  const raw = read(session, NEXT_KEY);
  write(session, NEXT_KEY, null);
  if (!raw) return null;
  try {
    const { path, at } = JSON.parse(raw) as { path?: unknown; at?: unknown };
    if (typeof at !== 'number' || Date.now() - at > NEXT_MAX_AGE_MS) return null;
    return safeNextPath(typeof path === 'string' ? path : null);
  } catch {
    return null;
  }
}

export const hasSignedInBefore = (): boolean => read(local, SIGNED_IN_BEFORE_KEY) === '1';
export const consentWasSkipped = (): boolean => read(session, CONSENT_SKIPPED_KEY) === '1';
export const setConsentSkipped = (skipped: boolean): void => write(session, CONSENT_SKIPPED_KEY, skipped ? '1' : null);

/** Called once a signed-in page loads: this device has signed in, and no consent retry is pending. */
export function markSignedIn(): void {
  write(local, SIGNED_IN_BEFORE_KEY, '1');
  setConsentSkipped(false);
}
