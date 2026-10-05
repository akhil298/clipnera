import { del, entries, set } from 'idb-keyval';

import type { UploadTarget } from './types';

/**
 * Uploads in progress, kept in IndexedDB so a reload can pick up where the
 * parts stopped (presigned part URLs live for 6 hours). Storage can be refused
 * (private windows, blocked site data); then an upload simply can't survive a
 * reload, which is what the beforeunload warning is for.
 */
const PREFIX = 'cn.upload:';

export interface PersistedUpload {
  id: string;
  kind: string;
  name: string;
  file: File;
  target: UploadTarget;
  /** [part number, ETag] for parts already in S3. */
  done: Array<[number, string]>;
  meta: unknown;
}

export async function saveUpload(record: PersistedUpload): Promise<void> {
  try {
    await set(PREFIX + record.id, record);
  } catch {
    // Not kept: the upload still runs, it just can't resume after a reload.
  }
}

export async function forgetUpload(id: string): Promise<void> {
  try {
    await del(PREFIX + id);
  } catch {
    // Nothing to clean up if storage was refused.
  }
}

export async function loadUploads(): Promise<PersistedUpload[]> {
  try {
    const all = await entries<string, PersistedUpload>();
    return all.filter(([key]) => typeof key === 'string' && key.startsWith(PREFIX)).map(([, record]) => record);
  } catch {
    return [];
  }
}
