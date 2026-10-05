import { del as idbDel, get as idbGet } from 'idb-keyval';

import { PENDING_UPLOAD_FILE_KEY } from '@/components/home/handoff';

/** Written by Home's composer (components/home/handoff.ts `savePendingUpload`). */
const PENDING_UPLOAD_KEY = 'cn.pendingUpload';

export interface UploadHandoff {
  prompt: string;
  url: string | null;
  file: File | null;
}

function takePrompt(): string {
  try {
    const raw = sessionStorage.getItem(PENDING_UPLOAD_KEY);
    sessionStorage.removeItem(PENDING_UPLOAD_KEY);
    if (!raw) return '';
    const parsed = JSON.parse(raw) as { prompt?: unknown };
    return typeof parsed.prompt === 'string' ? parsed.prompt : '';
  } catch {
    return '';
  }
}

async function takeFile(): Promise<File | null> {
  try {
    const file = await idbGet<File>(PENDING_UPLOAD_FILE_KEY);
    await idbDel(PENDING_UPLOAD_FILE_KEY);
    return file instanceof File ? file : null;
  } catch {
    return null;
  }
}

/**
 * What the person brought from elsewhere, read once and cleared: Home's prompt
 * and dropped file, and `?url=` / `?prompt=` from links such as Projects' empty
 * state. The query wins over storage when both are present.
 */
export async function takeUploadHandoff(params: URLSearchParams): Promise<UploadHandoff> {
  const stored = takePrompt();
  const file = await takeFile();
  return {
    prompt: params.get('prompt') ?? stored,
    url: params.get('url'),
    file,
  };
}
