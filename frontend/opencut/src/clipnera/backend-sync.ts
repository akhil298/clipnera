/**
 * Saves a Clipnera project from the studio: every change to the scene becomes Timeline
 * operations sent to /editor/projects/{id}/ops, and every imported file is uploaded to the
 * project first. The server's copy is the source of truth, so the AI agent sees what the user
 * sees, and an edit someone else saved first is merged in instead of overwritten.
 */

import { toast } from "sonner";
import type { EditorCore } from "@opencut/core";
import type { MediaAsset } from "@opencut/media/types";
import { ApiError, editorApi, type EditorAssetType } from "@/lib/api";
import { type Asset, applyOps, normalise, type Timeline, type TimelineOp, TimelineError } from "@/lib/editor/timeline";
import { assetFor, sceneToTimeline, timelineToScene } from "./bridge";
import { diffTimelines } from "./diff";
import { loadMedia } from "./media";

export type SyncStatus = "saved" | "saving" | "offline" | "error";

/** One file on its way to the project: ``share`` is 0..1 of it sent. */
export interface UploadProgress {
	id: string;
	name: string;
	share: number;
}

const DEBOUNCE_MS = 700;
// Refusals that mean "the project moved on": reload it and put our edit on top if it still fits.
const RELOAD_CODES: ReadonlySet<string> = new Set(["STALE_VERSION", "CONFLICT"]);
const RETRY_MS = 5000;
const UPLOADABLE: ReadonlySet<string> = new Set<EditorAssetType>([
	"video/mp4", "video/quicktime", "video/webm",
	"image/jpeg", "image/png", "image/webp", "image/gif",
	"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/x-m4a", "audio/webm", "audio/ogg",
]);

export class BackendSync {
	private status: SyncStatus = "saved";
	private listeners = new Set<() => void>();
	// Told the moment the user changes the timeline by hand (a running AI plan pauses on it).
	private editListeners = new Set<() => void>();
	private refreshing = false;
	private unsubscribers: Array<() => void> = [];
	private timer: ReturnType<typeof setTimeout> | null = null;
	private sending = false;
	private changedWhileSending = false;
	// Media being uploaded, and uploaded media whose add_asset hasn't been saved yet.
	private uploading = new Map<string, UploadProgress>();
	private uploaded = new Map<string, Asset>();
	private failedUploads = new Set<string>();

	constructor(
		private editor: EditorCore,
		private projectId: string,
		private version: number,
		private saved: Timeline,
		// Items on the server the studio doesn't show; saving leaves them be.
		private unshown: Set<string>,
	) {}

	start(): void {
		if (this.unsubscribers.length) return;
		const changed = () => {
			// No debounce for the pause signal: a running plan should stop within a few hundred ms (11.5.4).
			if (!this.refreshing && this.editListeners.size) this.notifyIfEdited();
			this.schedule();
		};
		this.unsubscribers = [
			this.editor.scenes.subscribe(changed),
			this.editor.timeline.subscribe(changed),
			this.editor.media.subscribe(changed),
			this.editor.project.subscribe(changed),
		];
	}

	stop(): void {
		for (const unsubscribe of this.unsubscribers) unsubscribe();
		this.unsubscribers = [];
		if (this.timer) clearTimeout(this.timer);
		this.timer = null;
	}

	getProjectId(): string {
		return this.projectId;
	}

	/** The project's frame rate on the server; the studio's playhead converts to it. */
	getFps(): number {
		return this.saved.fps;
	}

	onLocalEdit(listener: () => void): () => void {
		this.editListeners.add(listener);
		return () => this.editListeners.delete(listener);
	}

	getStatus(): SyncStatus {
		return this.status;
	}

	/** Files still being sent to the project. */
	getUploads(): UploadProgress[] {
		return [...this.uploading.values()];
	}

	/** Whether this file is part of the saved project yet (so the AI can see it). */
	isSaved(mediaId: string): boolean {
		return Boolean(this.saved.assets[mediaId]);
	}

	hasFailedUpload(mediaId: string): boolean {
		return this.failedUploads.has(mediaId);
	}

	subscribe(listener: () => void): () => void {
		this.listeners.add(listener);
		return () => this.listeners.delete(listener);
	}

	/** Save whatever is waiting now, e.g. before leaving the page. */
	async flush(): Promise<void> {
		if (this.timer) clearTimeout(this.timer);
		this.timer = null;
		await this.save();
	}

	private notifyIfEdited(): void {
		const scene = this.editor.scenes.getActiveSceneOrNull();
		const project = this.editor.project.getActiveOrNull();
		if (!scene || !project) return;
		try {
			const next = sceneToTimeline({
				tracks: scene.tracks,
				canvas: { fps: this.saved.fps, ...project.settings.canvasSize },
				assets: { ...this.saved.assets, ...Object.fromEntries(this.uploaded) },
				base: this.saved,
			});
			if (diffTimelines({ prev: this.saved, next, keep: this.unshown }).length) {
				for (const listener of this.editListeners) listener();
			}
		} catch {
			// A half-made edit can't be compared yet; the next change will be.
		}
	}

	private schedule(delay = DEBOUNCE_MS): void {
		if (this.timer) clearTimeout(this.timer);
		this.timer = setTimeout(() => {
			this.timer = null;
			void this.save();
		}, delay);
	}

	private setStatus(status: SyncStatus): void {
		if (status === this.status) return;
		this.status = status;
		this.notify();
	}

	private notify(): void {
		for (const listener of this.listeners) listener();
	}

	private async save(): Promise<void> {
		if (this.sending) {
			this.changedWhileSending = true;
			return;
		}
		const scene = this.editor.scenes.getActiveSceneOrNull();
		const project = this.editor.project.getActiveOrNull();
		if (!scene || !project || this.editor.project.getIsLoading()) return;

		this.startUploads();
		let ops: TimelineOp[];
		try {
			const next = sceneToTimeline({
				tracks: scene.tracks,
				canvas: { fps: this.saved.fps, ...project.settings.canvasSize },
				assets: { ...this.saved.assets, ...Object.fromEntries(this.uploaded) },
				base: this.saved,
			});
			ops = diffTimelines({ prev: this.saved, next, keep: this.unshown });
		} catch (error) {
			this.fail(error);
			return;
		}
		if (!ops.length) {
			this.setStatus(this.uploading.size ? "saving" : "saved");
			return;
		}

		this.sending = true;
		this.setStatus("saving");
		try {
			await this.send(ops);
			this.setStatus(this.uploading.size ? "saving" : "saved");
		} catch (error) {
			if (isOffline(error)) {
				this.setStatus("offline");
				this.schedule(RETRY_MS);
			} else {
				this.fail(error);
			}
		} finally {
			this.sending = false;
			if (this.changedWhileSending) {
				this.changedWhileSending = false;
				this.schedule(0);
			}
		}
	}

	private async send(ops: TimelineOp[]): Promise<void> {
		const base = this.version;
		try {
			const result = await editorApi.applyOps(this.projectId, { base_version: base, ops });
			this.accept(result.version, result.timeline);
		} catch (error) {
			if (!(error instanceof ApiError && RELOAD_CODES.has(error.code ?? ""))) throw error;
			// CONFLICT: a person changed the same thing since; their change stands.
			await this.rebase(ops, error.code === "CONFLICT");
			return;
		}
		// The server put our ops on top of changes made since (the agent, another tab): show those
		// too, or the next save would undo them.
		if (this.version !== base + 1) await this.refresh();
	}

	/** Show the server's current copy, e.g. after the AI changed the project. */
	async refresh(): Promise<void> {
		const fresh = await editorApi.get(this.projectId);
		this.accept(fresh.version, fresh.timeline);
		await this.show(this.saved, fresh.asset_urls);
	}

	/**
	 * Someone (the agent, another tab) saved first. Our ops go on top of their version when they
	 * still apply and don't clash; otherwise theirs wins and the studio shows it.
	 */
	private async rebase(ops: TimelineOp[], clashed: boolean): Promise<void> {
		const fresh = await editorApi.get(this.projectId);
		const theirs = normalise(fresh.timeline);
		let merged: Timeline | null = null;
		try {
			merged = clashed ? null : applyOps(theirs, ops);
		} catch (error) {
			if (!(error instanceof TimelineError)) throw error;
		}
		if (merged) {
			const result = await editorApi.applyOps(this.projectId, { base_version: fresh.version, ops });
			this.accept(result.version, result.timeline);
		} else {
			this.accept(fresh.version, fresh.timeline);
			toast.warning("This project changed somewhere else", {
				description: "Your last edit clashed with it, so the studio now shows the saved version.",
			});
		}
		await this.show(this.saved, fresh.asset_urls);
	}

	private accept(version: number, timeline: Timeline): void {
		this.version = version;
		this.saved = normalise(timeline);
		for (const id of this.uploaded.keys()) {
			if (this.saved.assets[id]) this.uploaded.delete(id);
		}
		this.notify();
	}

	/** Put a Timeline from the server on screen, loading any media the browser doesn't have yet. */
	private async show(timeline: Timeline, urls: Record<string, string>): Promise<void> {
		const media = await loadMedia({
			projectId: this.projectId,
			assets: Object.values(timeline.assets),
			urls,
			have: this.editor.media.getAssets(),
		});
		const known = new Set(this.editor.media.getAssets().map((asset) => asset.id));
		const added = [...media.values()].filter((asset) => !known.has(asset.id));
		if (added.length) this.editor.media.setAssets({ assets: [...this.editor.media.getAssets(), ...added] });
		const { tracks, unshown } = timelineToScene({ timeline, media });
		this.unshown = unshown;
		this.refreshing = true;
		try {
			this.editor.timeline.updateTracks(tracks);
		} finally {
			this.refreshing = false;
		}
	}

	private startUploads(): void {
		for (const media of this.editor.media.getAssets()) {
			const known = this.saved.assets[media.id] || this.uploaded.has(media.id);
			if (known || this.uploading.has(media.id) || this.failedUploads.has(media.id)) continue;
			void this.upload(media);
		}
	}

	private async upload(media: MediaAsset): Promise<void> {
		const type = media.file.type;
		if (!UPLOADABLE.has(type)) {
			this.failedUploads.add(media.id);
			toast.error(`${media.name} can't be saved to your project`, {
				description: "Use MP4, MOV or WebM video, JPEG, PNG, WebP or GIF images, or MP3, WAV, M4A, WebM or OGG audio.",
			});
			return;
		}
		const progress: UploadProgress = { id: media.id, name: media.name, share: 0 };
		this.uploading.set(media.id, progress);
		this.setStatus("saving");
		this.notify();
		const toastId = toast.loading(`Uploading ${media.name}…`);
		try {
			const key = await editorApi.uploadAsset(this.projectId, media.file, type as EditorAssetType, (share) => {
				this.uploading.set(media.id, { ...progress, share });
				this.notify();
				toast.loading(`Uploading ${media.name} — ${Math.round(share * 100)}%`, { id: toastId });
			});
			this.uploaded.set(media.id, assetFor({ media, key, fps: this.saved.fps }));
			toast.success(`${media.name} is saved to your project`, { id: toastId });
		} catch (error) {
			this.failedUploads.add(media.id);
			toast.error(`Couldn't upload ${media.name}`, {
				id: toastId,
				description: error instanceof Error ? error.message : undefined,
			});
		} finally {
			this.uploading.delete(media.id);
			this.notify();
			this.schedule(0);
		}
	}

	private fail(error: unknown): void {
		console.error("Saving the project failed:", error);
		this.setStatus("error");
		toast.error("Couldn't save your last edit", {
			id: "clipnera-save-error",
			description: error instanceof Error ? error.message : undefined,
		});
	}
}

function isOffline(error: unknown): boolean {
	return (typeof navigator !== "undefined" && !navigator.onLine) || error instanceof TypeError;
}
