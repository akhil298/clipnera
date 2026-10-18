/**
 * What the studio agent does in the studio itself: move the playhead, select items, play a range
 * in the preview, open a side panel. The backend streams these as `ui` events (brain/studio.py);
 * none of them changes the project, so none enters the undo history or is saved.
 */

import { EditorCore } from "@opencut/core";
import { useAssetsPanelStore } from "@opencut/components/editor/panels/assets/assets-panel-store";
import type { ElementRef } from "@opencut/timeline/types";
import type { AgentEvent } from "@/lib/api";
import { toTicks } from "./bridge";

type AgentUi = Extract<AgentEvent, { event: "ui" }>["data"];

// The range the agent asked to play; a newer one replaces it.
let stopPlaying: (() => void) | null = null;

const ticksAt = (seconds: number, fps: number) => toTicks(Math.round(seconds * fps), fps);

/** Item ids as the studio's element refs; ids not on the timeline are left out. */
function refsFor(itemIds: string[]): ElementRef[] {
	const scene = EditorCore.getInstance().scenes.getActiveSceneOrNull();
	if (!scene) return [];
	const tracks = [scene.tracks.main, ...scene.tracks.overlay, ...scene.tracks.audio];
	return tracks.flatMap((track) =>
		track.elements.filter((element) => itemIds.includes(element.id)).map((element) => ({ trackId: track.id, elementId: element.id })),
	);
}

/** Play from ``start`` and pause at ``end`` (seconds), unless the user takes over first. */
function playRange(start: number, end: number, fps: number): void {
	const playback = EditorCore.getInstance().playback;
	stopPlaying?.();
	const until = ticksAt(end, fps);
	playback.seek({ time: ticksAt(start, fps) });
	playback.play();
	const offTime = playback.onUpdate((time) => {
		if (time >= until) stopPlaying?.();
	});
	// Paused, or the user played something else.
	const offState = playback.subscribe(() => {
		if (!playback.getIsPlaying()) stopPlaying?.();
	});
	stopPlaying = () => {
		offTime();
		offState();
		stopPlaying = null;
		if (playback.getIsPlaying()) playback.pause();
	};
}

export function actOn(ui: AgentUi, fps: number): void {
	const editor = EditorCore.getInstance();
	if (ui.action === "seek" && ui.seconds !== null) editor.playback.seek({ time: ticksAt(ui.seconds, fps) });
	if (ui.action === "select") editor.selection.setSelectedElements({ elements: refsFor(ui.item_ids) });
	if (ui.action === "play" && ui.seconds !== null && ui.end !== null) playRange(ui.seconds, ui.end, fps);
	if (ui.action === "panel" && ui.panel) useAssetsPanelStore.getState().setActiveTab(ui.panel);
}
