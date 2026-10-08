import { create } from 'zustand';

import { isApiError } from '@/lib/api/errors';

import { PartUrlExpiredError, sendParts } from './parts';
import { forgetUpload, loadUploads, saveUpload } from './persist';
import type { UploadKind, UploadTarget, UploadTask } from './types';

/**
 * Every upload in this tab. The store lives at module level, so uploads keep
 * going across client navigation (the New video dialog closes and routes to
 * the project while its file is still sending). Components read it through
 * the hooks in `useUploads.ts`; the actions below are plain functions.
 */
export const useUploadStore = create<{ tasks: Record<string, UploadTask> }>(() => ({ tasks: {} }));

interface Runtime {
  file: File;
  kind: UploadKind<unknown>;
  meta: unknown;
  target: UploadTarget | null;
  done: Map<number, string>;
  controller: AbortController | null;
  /** `complete` succeeded; nothing is left to send or abort. */
  uploaded: boolean;
}

const kinds = new Map<string, UploadKind<unknown>>();
const runtime = new Map<string, Runtime>();
const PROGRESS_EVERY_MS = 250;

/** Registers a kind so its persisted uploads can resume after a reload. Call once at module level. */
export function defineUploadKind<M>(kind: UploadKind<M>): UploadKind<M> {
  kinds.set(kind.kind, kind as UploadKind<unknown>);
  return kind;
}

const getTask = (id: string): UploadTask | undefined => useUploadStore.getState().tasks[id];

function patch(id: string, partial: Partial<UploadTask>) {
  useUploadStore.setState((state) => {
    const task = state.tasks[id];
    return task ? { tasks: { ...state.tasks, [id]: { ...task, ...partial } } } : state;
  });
}

function remove(id: string) {
  runtime.delete(id);
  useUploadStore.setState((state) => {
    const { [id]: _removed, ...rest } = state.tasks;
    return { tasks: rest };
  });
}

function persist(id: string) {
  const rt = runtime.get(id);
  const task = getTask(id);
  if (!rt?.target || !task || rt.uploaded) return;
  void saveUpload({ id, kind: task.kind, name: task.name, file: rt.file, target: rt.target, done: [...rt.done], meta: rt.meta });
}

function describe(err: unknown): string {
  if (err instanceof PartUrlExpiredError) return 'The upload link expired. Start a new video to send this file again.';
  if (isApiError(err)) return err.message;
  if (err instanceof Error && err.message) return err.message;
  return 'Something went wrong. Try again.';
}

const isAbort = (err: unknown) => err instanceof DOMException && err.name === 'AbortError';

async function transfer(id: string) {
  const rt = runtime.get(id);
  if (!rt?.target) return;
  const controller = new AbortController();
  rt.controller = controller;
  patch(id, { phase: 'uploading', error: null, step: null });

  let sample = { at: performance.now(), bytes: getTask(id)?.sentBytes ?? 0 };
  let lastPaint = 0;
  try {
    const parts = await sendParts({
      file: rt.file,
      plan: rt.target.plan,
      done: rt.done,
      signal: controller.signal,
      onPartDone: () => persist(id),
      onProgress: (sentBytes) => {
        const now = performance.now();
        if (now - lastPaint < PROGRESS_EVERY_MS) return;
        lastPaint = now;
        const elapsed = (now - sample.at) / 1000;
        const rate = elapsed >= 1 ? Math.max(0, (sentBytes - sample.bytes) / elapsed) : getTask(id)?.bytesPerSecond ?? null;
        if (elapsed >= 1) sample = { at: now, bytes: sentBytes };
        patch(id, { sentBytes, bytesPerSecond: rate });
      },
    });
    patch(id, { sentBytes: rt.file.size, bytesPerSecond: null, phase: 'processing', step: 'Finishing the upload' });
    await rt.kind.complete(rt.target, parts, rt.meta);
    rt.uploaded = true;
    void forgetUpload(id);
    patch(id, { phase: 'done', step: null });
  } catch (err) {
    if (controller.signal.aborted && isAbort(err)) return;
    patch(id, { phase: 'failed', bytesPerSecond: null, step: null, error: describe(err) });
  }
}

/**
 * Opens the upload on the server and starts sending. Resolves as soon as the
 * server has answered `begin` (so the caller can route to the new resource);
 * the bytes keep flowing in the background. A refused `begin` rejects and
 * leaves no task behind.
 */
export async function startUpload<M>(kind: UploadKind<M>, file: File, meta: M): Promise<UploadTask> {
  const id = crypto.randomUUID();
  useUploadStore.setState((state) => ({
    tasks: {
      ...state.tasks,
      [id]: { id, kind: kind.kind, name: file.name, size: file.size, sentBytes: 0, phase: 'queued', bytesPerSecond: null, step: null, error: null, targetId: null, meta },
    },
  }));
  const rt: Runtime = { file, kind: kind as UploadKind<unknown>, meta, target: null, done: new Map(), controller: null, uploaded: false };
  runtime.set(id, rt);
  try {
    rt.target = await kind.begin(file, meta);
  } catch (err) {
    remove(id);
    throw err;
  }
  patch(id, { targetId: rt.target.id });
  persist(id);
  void transfer(id);
  return getTask(id)!;
}

/** Stops sending; parts already in S3 are kept. */
export function pauseUpload(id: string) {
  const rt = runtime.get(id);
  if (getTask(id)?.phase !== 'uploading' || !rt) return;
  rt.controller?.abort();
  patch(id, { phase: 'paused', bytesPerSecond: null });
  persist(id);
}

/** Continues a paused upload, or tries a failed one again from where it stopped. */
export function resumeUpload(id: string) {
  const rt = runtime.get(id);
  const phase = getTask(id)?.phase;
  if (!rt || (phase !== 'paused' && phase !== 'failed')) return;
  if (!rt.uploaded) void transfer(id);
}

/** Stops for good, tells the server to drop the parts, and removes the task. */
export function cancelUpload(id: string) {
  const rt = runtime.get(id);
  if (!rt) return;
  rt.controller?.abort();
  if (rt.target && !rt.uploaded) void rt.kind.abort(rt.target).catch(() => undefined);
  void forgetUpload(id);
  remove(id);
}

/** Clears a finished or failed task from the list. */
export function dismissUpload(id: string) {
  const phase = getTask(id)?.phase;
  if (phase !== 'done' && phase !== 'failed') return;
  void forgetUpload(id);
  remove(id);
}

/** Calls `listener` once when the task ends: done, failed or cancelled (undefined). */
export function onUploadSettled(id: string, listener: (task: UploadTask | undefined) => void): () => void {
  let previous = getTask(id)?.phase;
  const unsubscribe = useUploadStore.subscribe((state) => {
    const task = state.tasks[id];
    if (task?.phase === previous) return;
    previous = task?.phase;
    if (!task || task.phase === 'done' || task.phase === 'failed') {
      unsubscribe();
      listener(task);
    }
  });
  return unsubscribe;
}

let restoring: Promise<void> | null = null;

/** Brings back uploads a reload interrupted, paused, so the person decides to continue. Runs once per tab. */
export function restoreUploads(): Promise<void> {
  restoring ??= loadUploads().then((records) => {
    for (const record of records) {
      const kind = kinds.get(record.kind);
      if (!kind || runtime.has(record.id)) continue;
      const done = new Map(record.done);
      const sentBytes = Math.min(record.file.size, done.size * record.target.plan.partSize);
      runtime.set(record.id, { file: record.file, kind, meta: record.meta, target: record.target, done, controller: null, uploaded: false });
      useUploadStore.setState((state) => ({
        tasks: {
          ...state.tasks,
          [record.id]: {
            id: record.id, kind: record.kind, name: record.name, size: record.file.size, sentBytes,
            phase: 'paused', bytesPerSecond: null, step: null, error: null, targetId: record.target.id, meta: record.meta,
          },
        },
      }));
    }
  });
  return restoring;
}

/** Leaving the page now would lose the upload, so the browser asks first. */
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', (event) => {
    const busy = Object.values(useUploadStore.getState().tasks).some((task) => task.phase === 'queued' || task.phase === 'uploading' || task.phase === 'processing');
    if (busy) event.preventDefault();
  });
}
