/**
 * Pending hand edits on top of the server's Timeline (docs/revamp/architecture/frontend.md §5.2).
 * Pure: the doc store calls these; tests run them directly.
 */
import { applyOps, TimelineError, type Item, type Timeline, type TimelineOp, type Track } from './timeline';

/** One gesture: applied locally at once, sent as one `POST …/ops`, acked or dropped as a whole. */
export interface PendingBatch {
  id: string;
  ops: TimelineOp[];
  /** Plain name of what it changed ("Title 2"), for the "replaced" toast. */
  label?: string;
  createdAt: number;
}

/** A batch that no longer applies after the server moved on. */
export interface DroppedBatch {
  batch: PendingBatch;
  code: string;
  message: string;
}

export interface RebaseResult {
  view: Timeline;
  kept: PendingBatch[];
  dropped: DroppedBatch[];
}

/** Re-apply every pending batch, in order, on `server`. A batch that fails is dropped; the rest still apply. */
export function rebase(server: Timeline, pending: readonly PendingBatch[]): RebaseResult {
  let view = server;
  const kept: PendingBatch[] = [];
  const dropped: DroppedBatch[] = [];
  for (const batch of pending) {
    try {
      view = applyOps(view, batch.ops);
      kept.push(batch);
    } catch (error) {
      if (!(error instanceof TimelineError)) throw error;
      dropped.push({ batch, code: error.code, message: error.message });
    }
  }
  return { view, kept, dropped };
}

/** What a remote revision means for a document at `version` (events.md §3.3 invariant 2, §7.3). */
export type RemoteFit = 'duplicate' | 'next' | 'gap';

export const fitRemote = (version: number, base: number, revision: number): RemoteFit =>
  revision <= version ? 'duplicate' : base === version ? 'next' : 'gap';

/** Item ids an op names, for locks, markers and toasts. */
export function opItemIds(op: TimelineOp): string[] {
  switch (op.op) {
    case 'add_item':
      return [op.item.id];
    case 'split_item':
      return [op.item, op.new_id];
    case 'remove_item':
    case 'move_item':
    case 'trim_item':
    case 'update_item':
    case 'replace_asset':
      return [op.item];
    default:
      return [];
  }
}

export const batchItemIds = (ops: readonly TimelineOp[]): string[] => Array.from(new Set(ops.flatMap(opItemIds)));

function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  return keysA.every((key) => sameValue((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]));
}

/**
 * `applyOps` clones the whole document, so every item would be a new object after any edit.
 * This hands back `prev`'s objects wherever nothing changed, so a selector over one item or
 * track re-renders only when that item or track changed.
 */
export function shareUnchanged(prev: Timeline | null, next: Timeline): Timeline {
  if (!prev) return next;
  if (prev === next) return prev;
  const prevItems = new Map<string, Item>();
  for (const track of prev.tracks) for (const item of track.items) prevItems.set(item.id, item);
  const prevTracks = new Map(prev.tracks.map((track) => [track.id, track]));

  const tracks = next.tracks.map((track): Track => {
    const items = track.items.map((item) => {
      const old = prevItems.get(item.id);
      return old && sameValue(old, item) ? old : item;
    });
    const old = prevTracks.get(track.id);
    const same =
      old && old.kind === track.kind && old.muted === track.muted && old.items.length === items.length && old.items.every((item, i) => item === items[i]);
    return same ? old : { ...track, items };
  });

  const shared: Timeline = {
    ...next,
    assets: sameValue(prev.assets, next.assets) ? prev.assets : next.assets,
    captions: sameValue(prev.captions, next.captions) ? prev.captions : next.captions,
    markers: sameValue(prev.markers, next.markers) ? prev.markers : next.markers,
    tracks: tracks.length === prev.tracks.length && tracks.every((track, i) => track === prev.tracks[i]) ? prev.tracks : tracks,
  };
  const unchanged = (Object.keys(shared) as (keyof Timeline)[]).every((key) => shared[key] === prev[key]);
  return unchanged ? prev : shared;
}
