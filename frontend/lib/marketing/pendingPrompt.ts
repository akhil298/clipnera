/**
 * The landing hero's draft, carried through sign-in. Home reads the same key
 * once and clears it (components/home/handoff.ts `takePendingPrompt`).
 */
export const PENDING_PROMPT_KEY = 'cn.pendingPrompt';

export interface PendingPrompt {
  text: string;
  /** The YouTube link attached as a chip, if any. */
  url?: string;
  /** Epoch milliseconds; Home drops drafts older than a day. */
  createdAt: number;
}

/** Saves the draft; false when the browser refuses storage (private window, blocked site data). */
export function savePendingPrompt(text: string, url?: string): boolean {
  const draft: PendingPrompt = { text: text.trim(), ...(url ? { url } : {}), createdAt: Date.now() };
  try {
    sessionStorage.setItem(PENDING_PROMPT_KEY, JSON.stringify(draft));
    return true;
  } catch {
    return false;
  }
}
