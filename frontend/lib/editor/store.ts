/**
 * The editor's document store (docs/revamp/architecture/frontend.md §5.1–§5.2).
 *
 * `server` is the last acked Timeline and version; `pending` are hand-edit batches not yet acked;
 * `view` = server + pending, which is what every zone renders. Batches go to the server one at a
 * time, each on the last acked version. A 409 STALE_VERSION or a remote revision rebases the
 * pending batches by re-applying them (ops address items by id); a batch that no longer applies is
 * dropped and reported in `dropped` for the "Your edit to X was replaced" toast. Unacked batches
 * are kept in IndexedDB so a reload or crash loses nothing.
 *
 * Playback time is deliberately not here: it lives in lib/editor/playback/clock.ts outside React,
 * so nothing that reads this store re-renders per frame. Views keep unchanged items' identity
 * (`shareUnchanged`), so `selectItem(id)` re-renders only when that item changes.
 *
 * Network and storage are injected (`DocTransport`, `PendingStorage`), so this file runs under
 * `node --test`; lib/api/editor/transport.ts is the real transport.
 */
import { del, get, set } from 'idb-keyval';
import { useStore } from 'zustand';
import { createStore, type StoreApi } from 'zustand/vanilla';

import { batchItemIds, fitRemote, rebase, shareUnchanged, type DroppedBatch, type PendingBatch } from './rebase';
import { applyOps, duration, findItem, TimelineError, type Item, type Timeline, type TimelineOp, type Track } from './timeline';

export type { DroppedBatch, PendingBatch } from './rebase';

export interface ServerDoc {
  timeline: Timeline;
  version: number;
}

export interface DocTransport {
  /** `POST /editor/projects/{id}/ops`; rejects with an error carrying `code` (`STALE_VERSION`) and `status`. */
  sendOps(projectId: string, baseVersion: number, ops: TimelineOp[]): Promise<ServerDoc>;
  /** The current server document, for resync (until EB-2 `ops?since=` exists this is a full GET). */
  fetchProject(projectId: string): Promise<ServerDoc>;
}

export interface PendingStorage {
  load(projectId: string): Promise<PendingBatch[]>;
  save(projectId: string, batches: PendingBatch[]): Promise<void>;
}

/** Saved · Saving · Not saved (with Retry) · Offline (kept on this device). 02-editor §2.1. */
export type SaveState = 'saved' | 'saving' | 'error' | 'offline';

/** Amber landing: items and frame ranges a revision touched; `key` restarts the 600 ms outline. */
export interface Landing {
  itemIds: string[];
  ranges: [number, number][];
  revision: number;
  key: number;
}

export interface DocState {
  projectId: string | null;
  server: ServerDoc | null;
  pending: PendingBatch[];
  /** server + pending: what the editor shows. Null until `hydrate`. */
  view: Timeline | null;
  save: SaveState;
  error: { code: string; message: string } | null;
  /** Edits a rebase threw away; the UI toasts each and calls `dismissDropped`. */
  dropped: DroppedBatch[];
  /** An earlier version shown read-only; the live document is untouched. */
  preview: { versionId: string; label: string; timeline: Timeline } | null;
  landed: Landing | null;
}

export type ApplyResult =
  | { ok: true; batchId: string }
  | { ok: false; code: 'NOT_READY' | 'READ_ONLY' | 'LOCKED' | string; message: string; itemIds: string[] };

export interface DocStoreDeps {
  transport: DocTransport;
  storage?: PendingStorage;
  /** Items the running step holds (run store `isLocked`); hand edits on them are refused before queueing. */
  isLocked?: (itemId: string) => boolean;
  newId?: () => string;
  now?: () => number;
}

export interface DocStore {
  store: StoreApi<DocState>;
  /** Load a project: restores this project's unsent batches from storage, rebases them, then sends them. */
  hydrate(projectId: string, doc: ServerDoc): Promise<void>;
  /** One gesture as one batch. Applied locally at once, then sent. */
  apply(ops: TimelineOp[], label?: string): ApplyResult;
  /** `run.operation.applied` (or another tab's revision). Duplicates are ignored; a gap resyncs. */
  applyRemote(change: { base_revision: number; revision: number; ops: TimelineOp[]; item_ids?: string[]; changed_ranges?: [number, number][] }): Promise<void>;
  /** Send whatever is pending (also on reconnect). Resolves when the queue is empty or blocked. */
  flush(): Promise<void>;
  /** Retry after "Not saved" or going back online. */
  retry(): Promise<void>;
  /** Refetch the server document and rebase pending batches on it (`sync.reset`, gaps, restore, undo). */
  resync(): Promise<void>;
  /** Replace the server document after a restore or undo that returned the new head. */
  replaceServer(doc: ServerDoc): void;
  viewVersion(versionId: string, label: string, timeline: Timeline): void;
  backToLatest(): void;
  dismissDropped(batchId: string): void;
}

const INITIAL: DocState = {
  projectId: null,
  server: null,
  pending: [],
  view: null,
  save: 'saved',
  error: null,
  dropped: [],
  preview: null,
  landed: null,
};

const errorCode = (error: unknown): string => {
  const code = (error as { code?: unknown } | null)?.code;
  return typeof code === 'string' ? code : '';
};
const errorStatus = (error: unknown): number | undefined => {
  const status = (error as { status?: unknown } | null)?.status;
  return typeof status === 'number' ? status : undefined;
};
const errorMessage = (error: unknown): string => (error instanceof Error ? error.message : 'Something went wrong');

/** No response, a timeout, a 5xx or a 429: keep the batch and wait for Retry. Mirrors `isRetryable`. */
const isTransient = (error: unknown): boolean => {
  const status = errorStatus(error);
  return status === undefined || status === 0 || status === 429 || status >= 500;
};

export function createDocStore(deps: DocStoreDeps): DocStore {
  const store = createStore<DocState>(() => INITIAL);
  const newId = deps.newId ?? (() => crypto.randomUUID());
  const now = deps.now ?? Date.now;
  let sending: Promise<void> | null = null;
  let landingKey = 0;

  const persist = (state: DocState) => {
    if (deps.storage && state.projectId) void deps.storage.save(state.projectId, state.pending).catch(() => undefined);
  };

  /** Put a new server document under the pending batches. */
  const rebaseOnto = (server: ServerDoc, extra: Partial<DocState> = {}) => {
    const state = store.getState();
    const result = rebase(server.timeline, state.pending);
    const next: DocState = {
      ...state,
      ...extra,
      server,
      pending: result.kept,
      view: shareUnchanged(state.view, result.view),
      dropped: result.dropped.length ? [...state.dropped, ...result.dropped] : state.dropped,
    };
    store.setState(next, true);
    if (result.dropped.length) persist(next);
  };

  const resync = async () => {
    const { projectId } = store.getState();
    if (!projectId) return;
    rebaseOnto(await deps.transport.fetchProject(projectId));
  };

  const sendLoop = async () => {
    for (;;) {
      const state = store.getState();
      const batch = state.pending[0];
      if (!state.projectId || !state.server || !batch) {
        store.setState({ save: 'saved', error: null });
        return;
      }
      store.setState({ save: 'saving' });
      try {
        const acked = await deps.transport.sendOps(state.projectId, state.server.version, batch.ops);
        const current = store.getState();
        const pending = current.pending.filter((b) => b.id !== batch.id);
        const server = current.server && current.server.version >= acked.version ? current.server : acked;
        store.setState({ pending });
        rebaseOnto(server);
        persist(store.getState());
      } catch (error) {
        if (errorCode(error) === 'STALE_VERSION') {
          try {
            await resync();
          } catch (resyncError) {
            store.setState({ save: isTransient(resyncError) ? 'offline' : 'error', error: { code: errorCode(resyncError), message: errorMessage(resyncError) } });
            return;
          }
          continue;
        }
        if (isTransient(error)) {
          const offline = errorStatus(error) === 0 || errorStatus(error) === undefined;
          store.setState({ save: offline ? 'offline' : 'error', error: { code: errorCode(error), message: errorMessage(error) } });
          return;
        }
        // The server refused the batch itself (a rule broke): drop it and keep going.
        const current = store.getState();
        const next = {
          pending: current.pending.filter((b) => b.id !== batch.id),
          dropped: [...current.dropped, { batch, code: errorCode(error) || 'REFUSED', message: errorMessage(error) }],
          error: { code: errorCode(error), message: errorMessage(error) },
        };
        store.setState(next);
        if (current.server) rebaseOnto(current.server);
        persist(store.getState());
      }
    }
  };

  const flush = () => {
    sending ??= sendLoop().finally(() => {
      sending = null;
    });
    return sending;
  };

  return {
    store,

    async hydrate(projectId, doc) {
      const restored = deps.storage ? await deps.storage.load(projectId).catch(() => []) : [];
      store.setState({ ...INITIAL, projectId, pending: restored }, true);
      rebaseOnto(doc);
      await flush();
    },

    apply(ops, label) {
      const state = store.getState();
      if (!state.view || !state.server) return { ok: false, code: 'NOT_READY', message: 'The project is still loading.', itemIds: [] };
      if (state.preview) return { ok: false, code: 'READ_ONLY', message: 'Go back to the latest version to edit.', itemIds: [] };
      const itemIds = batchItemIds(ops);
      const locked = deps.isLocked ? itemIds.filter(deps.isLocked) : [];
      if (locked.length) return { ok: false, code: 'LOCKED', message: 'Clipnera is working on this. It unlocks when the step ends.', itemIds: locked };
      let view: Timeline;
      try {
        view = applyOps(state.view, ops);
      } catch (error) {
        if (error instanceof TimelineError) return { ok: false, code: error.code, message: error.message, itemIds };
        throw error;
      }
      const batch: PendingBatch = { id: newId(), ops, label, createdAt: now() };
      const next: DocState = { ...state, pending: [...state.pending, batch], view: shareUnchanged(state.view, view) };
      store.setState(next, true);
      persist(next);
      if (next.save !== 'offline') void flush();
      return { ok: true, batchId: batch.id };
    },

    async applyRemote(change) {
      const { server } = store.getState();
      if (!server) return;
      const fit = fitRemote(server.version, change.base_revision, change.revision);
      if (fit === 'duplicate') return;
      if (fit === 'gap') return resync();
      let timeline: Timeline;
      try {
        timeline = applyOps(server.timeline, change.ops);
      } catch {
        return resync();
      }
      rebaseOnto(
        { timeline, version: change.revision },
        { landed: { itemIds: change.item_ids ?? batchItemIds(change.ops), ranges: change.changed_ranges ?? [], revision: change.revision, key: ++landingKey } },
      );
    },

    flush,

    retry() {
      store.setState({ error: null });
      return flush();
    },

    resync,

    replaceServer(doc) {
      rebaseOnto(doc);
    },

    viewVersion(versionId, label, timeline) {
      store.setState({ preview: { versionId, label, timeline } });
    },

    backToLatest() {
      store.setState({ preview: null });
    },

    dismissDropped(batchId) {
      store.setState((state) => ({ dropped: state.dropped.filter((d) => d.batch.id !== batchId) }));
    },
  };
}

/** Pending batches in IndexedDB, one key per project (~0.6 KB of idb-keyval). */
export const idbPendingStorage: PendingStorage = {
  async load(projectId) {
    return ((await get<PendingBatch[]>(pendingKey(projectId))) ?? []).filter((b) => Array.isArray(b?.ops));
  },
  async save(projectId, batches) {
    if (batches.length) await set(pendingKey(projectId), batches);
    else await del(pendingKey(projectId));
  },
};

const pendingKey = (projectId: string) => `cn-editor-pending:${projectId}`;

/* ───────────── selectors (all return stable references) ───────────── */

/** What the timeline and preview draw: the preview document while viewing an earlier version. */
export const selectShown = (s: DocState): Timeline | null => s.preview?.timeline ?? s.view;
export const selectReadOnly = (s: DocState): boolean => s.preview !== null;
export const selectTracks = (s: DocState): Track[] => selectShown(s)?.tracks ?? EMPTY_TRACKS;
export const selectTrack = (trackId: string) => (s: DocState): Track | undefined => selectTracks(s).find((t) => t.id === trackId);
export const selectItem = (itemId: string) => (s: DocState): Item | undefined => {
  const doc = selectShown(s);
  if (!doc) return undefined;
  try {
    return findItem(doc, itemId)[1];
  } catch {
    return undefined;
  }
};
export const selectDurationFrames = (s: DocState): number => {
  const doc = selectShown(s);
  return doc ? duration(doc) : 0;
};
export const selectFps = (s: DocState): number => selectShown(s)?.fps ?? 30;
export const selectCaptions = (s: DocState) => selectShown(s)?.captions ?? null;
export const selectVersion = (s: DocState): number | null => s.server?.version ?? null;
export const selectSaveState = (s: DocState): SaveState => s.save;
export const selectHasPending = (s: DocState): boolean => s.pending.length > 0;
export const selectLanded = (s: DocState): Landing | null => s.landed;
export const selectDropped = (s: DocState): DroppedBatch[] => s.dropped;

const EMPTY_TRACKS: Track[] = [];

/** React binding: `useDoc(doc, selectItem(id))`. Selectors must return stable references (the ones above do). */
export function useDoc<T>(doc: DocStore, selector: (state: DocState) => T): T {
  return useStore(doc.store, selector);
}
