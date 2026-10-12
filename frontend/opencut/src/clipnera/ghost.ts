/**
 * Timeline markers for the AI: a plan's shots as dashed amber ranges while its card is open
 * (the ghost preview), and a marker where the agent is working while a plan runs.
 *
 * Drawn with OpenCut's bookmarks (they have a colour, a range and a note), tagged by their note
 * so they're easy to clear. Bookmarks aren't saved to Clipnera (the bridge only syncs tracks)
 * and are set without a command, so they never enter the user's undo history.
 */

import { EditorCore } from "@opencut/core";
import type { Bookmark } from "@opencut/timeline/types";
import type { GhostClip } from "@/lib/api";
import { toTicks } from "./bridge";

const GHOST_TAG = "AI plan · ";
const CURSOR_TAG = "AI working";
const GHOST_COLOUR = "#f59e0b";
const CURSOR_COLOUR = "#38bdf8";

function setBookmarks(change: (bookmarks: Bookmark[]) => Bookmark[]): void {
	const editor = EditorCore.getInstance();
	const scene = editor.scenes.getActiveSceneOrNull();
	if (!scene) return;
	const next = { ...scene, bookmarks: change(scene.bookmarks) };
	editor.scenes.setScenes({
		scenes: editor.scenes.getScenes().map((s) => (s.id === scene.id ? next : s)),
		activeSceneId: scene.id,
	});
}

const isOurs = (bookmark: Bookmark) =>
	bookmark.note?.startsWith(GHOST_TAG) || bookmark.note === CURSOR_TAG;

/** Show a plan's shots as ranges on the timeline ruler. */
export function showGhost(ghost: GhostClip[], fps: number): void {
	setBookmarks((bookmarks) => [
		...bookmarks.filter((b) => !b.note?.startsWith(GHOST_TAG)),
		...ghost.map((clip) => ({
			time: toTicks(clip.at, fps),
			duration: toTicks(Math.max(1, clip.end - clip.at), fps),
			note: `${GHOST_TAG}${clip.label}`,
			color: GHOST_COLOUR,
		})),
	]);
}

/** Put the agent cursor at the start of the first item it just changed. */
export function showCursor(itemIds: string[]): void {
	const editor = EditorCore.getInstance();
	const scene = editor.scenes.getActiveSceneOrNull();
	if (!scene) return;
	const tracks = [scene.tracks.main, ...scene.tracks.overlay, ...scene.tracks.audio];
	const element = tracks.flatMap((t) => t.elements as Array<{ id: string; startTime: number }>).find((e) => itemIds.includes(e.id));
	if (!element) return;
	setBookmarks((bookmarks) => [
		...bookmarks.filter((b) => b.note !== CURSOR_TAG),
		{ time: element.startTime as Bookmark["time"], note: CURSOR_TAG, color: CURSOR_COLOUR },
	]);
}

/** Remove every AI marker. */
export function clearAiMarkers(): void {
	setBookmarks((bookmarks) => bookmarks.filter((b) => !isOurs(b)));
}
