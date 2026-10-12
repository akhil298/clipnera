/**
 * The operations that turn the last saved Timeline into the one the studio now shows.
 *
 * Small ops first (move, trim, update), so the op log reads like the edits made. The backend
 * checks the Timeline after every op, so a swap of two clips can't be done one move at a time;
 * when the small ops don't apply cleanly, every changed item is removed and added back instead.
 */

import {
	applyOps,
	type Item,
	type ItemPatch,
	type Timeline,
	type TimelineOp,
	TimelineError,
	type Track,
} from "@/lib/editor/timeline";

type Placed = { track: string; item: Item };

/**
 * `keep` lists items on the backend the studio doesn't show; they are never removed, and
 * neither is a track that holds one.
 */
export function diffTimelines({
	prev,
	next,
	keep,
}: {
	prev: Timeline;
	next: Timeline;
	keep: ReadonlySet<string>;
}): TimelineOp[] {
	const head: TimelineOp[] = [
		...Object.values(next.assets)
			.filter((asset) => !prev.assets[asset.id])
			.map((asset): TimelineOp => ({ op: "add_asset", asset })),
		...trackOps(prev, next),
	];
	const tail = trackRemovals(prev, next, keep);
	if (next.width !== prev.width || next.height !== prev.height) {
		tail.push({ op: "set_project", width: next.width, height: next.height });
	}

	const items = itemOps(prev, next, keep);
	let ops = [...head, ...items.fine, ...tail];
	let result = tryApply(prev, ops);
	if (!result) {
		ops = [...head, ...items.rebuild, ...tail];
		result = applyOps(prev, ops); // A Timeline that can't be reached this way is a bug: let it throw.
	}
	const order = finalOrder(prev, next, keep);
	if (order.join("\n") !== result.tracks.map((t) => t.id).join("\n")) {
		ops.push({ op: "reorder_tracks", order });
	}
	return ops;
}

function tryApply(timeline: Timeline, ops: TimelineOp[]): Timeline | null {
	try {
		return applyOps(timeline, ops);
	} catch (error) {
		if (error instanceof TimelineError) return null;
		throw error;
	}
}

function trackOps(prev: Timeline, next: Timeline): TimelineOp[] {
	const before = new Map(prev.tracks.map((track) => [track.id, track]));
	const ops: TimelineOp[] = [];
	for (const track of next.tracks) {
		const old = before.get(track.id);
		if (!old) ops.push({ op: "add_track", id: track.id, kind: track.kind });
		const change: Partial<Pick<Track, "muted" | "hidden" | "extra">> = {};
		if (track.muted !== (old?.muted ?? false)) change.muted = track.muted;
		if (track.hidden !== (old?.hidden ?? false)) change.hidden = track.hidden;
		if (!sameJson(track.extra, old?.extra ?? {})) change.extra = track.extra;
		if (Object.keys(change).length) ops.push({ op: "update_track", track: track.id, ...change });
	}
	return ops;
}

function heldTracks(prev: Timeline, keep: ReadonlySet<string>): Set<string> {
	return new Set(prev.tracks.filter((t) => t.items.some((i) => keep.has(i.id))).map((t) => t.id));
}

function trackRemovals(prev: Timeline, next: Timeline, keep: ReadonlySet<string>): TimelineOp[] {
	const wanted = new Set(next.tracks.map((t) => t.id));
	const held = heldTracks(prev, keep);
	return prev.tracks
		.filter((t) => !wanted.has(t.id) && !held.has(t.id) && prev.captions?.follow !== t.id)
		.map((t): TimelineOp => ({ op: "remove_track", track: t.id }));
}

/** The studio's order, with tracks it doesn't show kept after the rest. */
function finalOrder(prev: Timeline, next: Timeline, keep: ReadonlySet<string>): string[] {
	const wanted = new Set(next.tracks.map((t) => t.id));
	const held = heldTracks(prev, keep);
	const kept = prev.tracks
		.filter((t) => !wanted.has(t.id) && (held.has(t.id) || prev.captions?.follow === t.id))
		.map((t) => t.id);
	return [...next.tracks.map((t) => t.id), ...kept];
}

function placed(timeline: Timeline): Map<string, Placed> {
	return new Map(
		timeline.tracks.flatMap((track) => track.items.map((item) => [item.id, { track: track.id, item }] as const)),
	);
}

function itemOps(
	prev: Timeline,
	next: Timeline,
	keep: ReadonlySet<string>,
): { fine: TimelineOp[]; rebuild: TimelineOp[] } {
	const before = placed(prev);
	const after = placed(next);
	const removes: TimelineOp[] = [];
	const updates: TimelineOp[] = [];
	const moves: TimelineOp[] = [];
	const adds: TimelineOp[] = [];
	const changed: Placed[] = [];

	for (const id of before.keys()) {
		if (!after.has(id) && !keep.has(id)) removes.push({ op: "remove_item", item: id });
	}
	for (const [id, now] of after) {
		const old = before.get(id);
		if (!old) {
			adds.push({ op: "add_item", track: now.track, item: now.item });
			continue;
		}
		const edits = itemEdits(old, now);
		if (!edits) continue;
		changed.push(now);
		if (edits.recreate) {
			removes.push({ op: "remove_item", item: id });
			adds.push({ op: "add_item", track: now.track, item: now.item });
			continue;
		}
		updates.push(...edits.updates);
		moves.push(...edits.moves);
	}

	const rebuild: TimelineOp[] = [
		...removes,
		...changed
			.filter((now) => !removes.some((op) => op.op === "remove_item" && op.item === now.item.id))
			.map((now): TimelineOp => ({ op: "remove_item", item: now.item.id })),
		...changed
			.filter((now) => !adds.some((op) => op.op === "add_item" && op.item.id === now.item.id))
			.map((now): TimelineOp => ({ op: "add_item", track: now.track, item: now.item })),
		...adds,
	];
	return { fine: [...removes, ...updates, ...moves, ...adds], rebuild };
}

/** How one item changed; `recreate` when a change has no op of its own (a new type or asset). */
function itemEdits(
	old: Placed,
	now: Placed,
): { updates: TimelineOp[]; moves: TimelineOp[]; recreate: boolean } | null {
	const a = old.item;
	const b = now.item;
	if (sameJson(a, b) && old.track === now.track) return null;
	if (a.type !== b.type || (a.type === "clip" && b.type === "clip" && a.asset !== b.asset)) {
		return { updates: [], moves: [], recreate: true };
	}
	if (a.type === "sfx" && b.type === "sfx" && a.name !== b.name) {
		return { updates: [], moves: [], recreate: true };
	}

	const updates: TimelineOp[] = [];
	if (a.type === "clip" && b.type === "clip" && (a.src_in !== b.src_in || a.src_out !== b.src_out)) {
		updates.push({ op: "trim_item", item: b.id, src_in: b.src_in, src_out: b.src_out });
	}
	const patch = patchOf(a, b);
	if (Object.keys(patch).length) updates.push({ op: "update_item", item: b.id, patch });

	const moves: TimelineOp[] =
		a.at !== b.at || old.track !== now.track
			? [{ op: "move_item", item: b.id, at: b.at, ...(old.track !== now.track ? { track: now.track } : {}) }]
			: [];
	return { updates, moves, recreate: false };
}

const PATCHABLE: ReadonlyArray<keyof ItemPatch> = ["speed", "volume", "transform", "text", "dur", "gain_db", "extra"];

function patchOf(a: Item, b: Item): ItemPatch {
	const patch: Record<string, unknown> = {};
	const before = a as unknown as Record<string, unknown>;
	const after = b as unknown as Record<string, unknown>;
	for (const field of PATCHABLE) {
		if (field in after && !sameJson(before[field], after[field])) patch[field] = after[field];
	}
	return patch as ItemPatch;
}

/** Equal as JSON, ignoring key order and undefined fields. */
export function sameJson(a: unknown, b: unknown): boolean {
	return stableJson(a) === stableJson(b);
}

function stableJson(value: unknown): string {
	return JSON.stringify(value, (_key, v) =>
		v && typeof v === "object" && !Array.isArray(v)
			? Object.fromEntries(Object.entries(v).sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0)))
			: v,
	);
}
