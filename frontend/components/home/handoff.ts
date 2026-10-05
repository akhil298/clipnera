import { set as idbSet } from 'idb-keyval';

import { PENDING_PROMPT_KEY } from '@/lib/marketing/pendingPrompt';

/**
 * What crosses page boundaries through the browser. Storage can be refused
 * (private windows, blocked site data), so every read and write is guarded and
 * a failure only loses the convenience, never the page.
 */

/** Read by the upload flow (`/dashboard/upload`), which picks the file. */
const PENDING_UPLOAD_KEY = 'cn.pendingUpload';
/** A video dropped on the composer, so the upload flow needn't ask for it again (IndexedDB: a File doesn't fit sessionStorage). */
export const PENDING_UPLOAD_FILE_KEY = 'cn.pendingUploadFile';

const PENDING_PROMPT_MAX_AGE_MS = 24 * 60 * 60_000;

export interface PendingPrompt {
  text: string;
  url?: string;
}

function readPendingPrompt(): PendingPrompt | null {
  try {
    const raw = sessionStorage.getItem(PENDING_PROMPT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { text?: unknown; url?: unknown; createdAt?: unknown };
    const createdAt = typeof parsed.createdAt === 'number' ? parsed.createdAt : Date.parse(String(parsed.createdAt));
    if (Number.isFinite(createdAt) && Date.now() - createdAt > PENDING_PROMPT_MAX_AGE_MS) return null;
    const text = typeof parsed.text === 'string' ? parsed.text.trim() : '';
    const url = typeof parsed.url === 'string' && parsed.url ? parsed.url : undefined;
    return text || url ? { text, url } : null;
  } catch {
    return null;
  }
}

/** The landing page's draft (written before sign-in), left in place: sign-in previews it, Home takes it. Older than a day counts as abandoned. */
export const peekPendingPrompt = readPendingPrompt;

/** The landing page's draft, once: it is removed as it is read. */
export function takePendingPrompt(): PendingPrompt | null {
  const pending = readPendingPrompt();
  try {
    sessionStorage.removeItem(PENDING_PROMPT_KEY);
  } catch {
    // Refused storage: nothing was kept to clear.
  }
  return pending;
}

/** Hands the typed prompt to the upload flow. */
export function savePendingUpload(prompt: string): void {
  try {
    sessionStorage.setItem(PENDING_UPLOAD_KEY, JSON.stringify({ prompt }));
  } catch {
    // The upload flow still works; the prompt just has to be typed again.
  }
}

/** Keeps a dropped video for the upload flow. */
export async function savePendingUploadFile(file: File): Promise<void> {
  try {
    await idbSet(PENDING_UPLOAD_FILE_KEY, file);
  } catch {
    // Refused storage: the upload flow asks for the file again.
  }
}
