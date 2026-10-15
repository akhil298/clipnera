/**
 * The AI's view of the project's files, for the chat: each file goes Uploading → Understanding
 * (step by step) → Ready, and the first time one is ready the AI says what it found in it.
 *
 * A prompt sent while files are still being understood waits here and is sent the moment they
 * are, so "drop a video and say what you want" works in one go.
 */

import { create } from "zustand";
import { EditorCore } from "@opencut/core";
import { AddMediaAssetCommand } from "@opencut/commands/media";
import { processMediaAssets } from "@opencut/media/processing";
import { type AnalysisFindings, editorApi, type MediaAnalysisResponse } from "@/lib/api";
import { useAiStore } from "./ai-store";
import type { BackendSync } from "./backend-sync";
import { getCurrentSync } from "./save-status";

export type FileState = "uploading" | "saving" | "waiting" | "understanding" | "ready" | "failed" | "upload_failed";

export interface FootageFile {
	id: string;
	name: string;
	state: FileState;
	// What to show under the name: "Uploading 40%", "Listening to what's said"…
	detail: string;
	// How far along it is, 0..1.
	progress: number;
	canRetry: boolean;
}

interface FootageState {
	files: FootageFile[];
	// A prompt waiting for the files to be understood.
	held: string | null;
	add: (files: File[]) => Promise<void>;
	ask: (prompt: string) => void;
	retry: (assetId: string) => Promise<void>;
}

const POLL_MS = 2500;
// What auto mode asks for when the user dropped files and said nothing: the whole video, edited.
const AUTO_PROMPT = "Edit the full video.";
// Opening a project with more ready files than this doesn't replay what was found in each.
const REPLAY_FILES = 3;
const STAGES: Record<string, string> = {
	shots: "Watching the picture, shot by shot",
	transcript: "Listening to what's said",
	music: "Finding the beat",
	moments: "Picking out the best moments",
};
// Share of the bar each phase ends at: the upload fills the first part, each analysis step a bit more.
const UPLOAD_SHARE = 0.4;
const STAGE_ORDER = ["shots", "transcript", "music", "moments"];
const UNSETTLED: ReadonlySet<FileState> = new Set(["uploading", "saving", "waiting", "understanding"]);

let analyses = new Map<string, MediaAnalysisResponse>();
// Files whose findings the chat has already shown, per project.
const announced = new Map<string, Set<string>>();
// Projects auto mode has already made a first edit for in this visit.
const autoStarted = new Set<string>();

export const useFootageStore = create<FootageState>((set, get) => ({
	files: [],
	held: null,

	async add(files) {
		const project = EditorCore.getInstance().project.getActiveOrNull();
		if (!project || !files.length) return;
		const editor = EditorCore.getInstance();
		// Into the library only: the AI places it, and what it places it may also change.
		for (const asset of await processMediaAssets({ files })) {
			editor.command.execute({ command: new AddMediaAssetCommand({ projectId: project.metadata.id, asset }) });
		}
	},

	ask(prompt) {
		const text = prompt.trim();
		if (!text) return;
		if (get().files.some((file) => UNSETTLED.has(file.state))) {
			const sync = getCurrentSync();
			if (sync) useAiStore.getState().note(sync.getProjectId(), text, "I'll start on that as soon as I've finished going through your files.");
			set({ held: text });
			return;
		}
		void useAiStore.getState().send(text);
	},

	async retry(assetId) {
		const sync = getCurrentSync();
		if (!sync) return;
		const row = await editorApi.retryAnalysis(sync.getProjectId(), assetId);
		analyses.set(row.asset_id, row);
		useFootageStore.setState({ files: describe(sync) });
	},
}));

/** Follow the open project's files until the studio closes it. Returns the stop function. */
export function watchFootage(sync: BackendSync): () => void {
	analyses = new Map();
	let stopped = false;
	let polling = false;
	const editor = EditorCore.getInstance();
	const projectId = sync.getProjectId();
	const seen = announced.get(projectId) ?? new Set<string>();
	announced.set(projectId, seen);

	let first = true;

	const render = () => {
		if (!stopped) useFootageStore.setState({ files: describe(sync) });
	};

	/** Once nothing is uploading or being understood: send the waiting prompt, or in auto mode start the first edit. */
	const release = () => {
		const { files, held } = useFootageStore.getState();
		if (files.some((file) => UNSETTLED.has(file.state))) return;
		const ai = useAiStore.getState();
		if (held) {
			useFootageStore.setState({ held: null });
			void ai.send(held, undefined, true);
			return;
		}
		// Only on an untouched project with something to cut, and only once.
		const ready = files.some((file) => file.state === "ready");
		if (!ai.auto || ai.busy || autoStarted.has(projectId) || !ready || !sync.isEmpty()) return;
		if ((ai.byProject[projectId] ?? []).some((message) => message.role === "user")) return;
		autoStarted.add(projectId);
		ai.note(projectId, null, "Auto mode is on, so I'm making a first edit now. You can pause it, undo it, or tell me what to change.");
		void ai.send(AUTO_PROMPT, undefined, true);
	};

	const poll = async () => {
		if (polling || stopped) return;
		polling = true;
		try {
			const rows = await editorApi.analysis(projectId);
			if (stopped) return;
			analyses = new Map(rows.map((row) => [row.asset_id, row]));
			render();
			const names = new Map(editor.media.getAssets().map((media) => [media.id, media.name]));
			const fresh = rows.filter((row) => row.status === "ready" && row.findings && !seen.has(row.asset_id) && names.has(row.asset_id));
			const quiet = first && fresh.length > REPLAY_FILES;
			first = false;
			for (const row of fresh) {
				seen.add(row.asset_id);
				if (quiet) continue;
				const { text, suggestions } = report(names.get(row.asset_id)!, row.findings!);
				useAiStore.getState().note(projectId, null, text, suggestions);
			}
			release();
		} catch {
			// The next tick tries again.
		} finally {
			polling = false;
		}
	};

	const unsubscribe = [sync.subscribe(render), editor.media.subscribe(render)];
	const timer = setInterval(() => {
		const files = useFootageStore.getState().files;
		// Nothing to wait for once every saved file is ready or failed.
		if (files.some((file) => file.state === "waiting" || file.state === "understanding")) void poll();
		else release();
	}, POLL_MS);
	render();
	void poll();

	return () => {
		stopped = true;
		clearInterval(timer);
		for (const stop of unsubscribe) stop();
		useFootageStore.setState({ files: [], held: null });
	};
}

function describe(sync: BackendSync): FootageFile[] {
	const uploads = new Map(sync.getUploads().map((upload) => [upload.id, upload]));
	return EditorCore.getInstance().media.getAssets().map((media) => {
		const file = (state: FileState, detail: string, progress: number, canRetry = false): FootageFile =>
			({ id: media.id, name: media.name, state, detail, progress, canRetry });
		const upload = uploads.get(media.id);
		if (upload) return file("uploading", `Uploading ${Math.round(upload.share * 100)}%`, upload.share * UPLOAD_SHARE);
		if (sync.hasFailedUpload(media.id)) return file("upload_failed", "Couldn't upload this file", 0);
		if (!sync.isSaved(media.id)) return file("saving", "Saving to your project", UPLOAD_SHARE);
		const row = analyses.get(media.id);
		if (!row || row.status === "pending") return file("waiting", "Waiting to be looked at", UPLOAD_SHARE);
		if (row.status === "running") {
			const step = Math.max(0, STAGE_ORDER.indexOf(row.stage ?? "")) + 1;
			const done = UPLOAD_SHARE + ((1 - UPLOAD_SHARE) * step) / (STAGE_ORDER.length + 1);
			return file("understanding", STAGES[row.stage ?? ""] ?? "Looking through it", done);
		}
		if (row.status === "failed") return file("failed", row.error ?? "Couldn't understand this file", 0, true);
		return file("ready", "Ready", 1);
	});
}

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

/** The chat message for one understood file. */
function report(name: string, found: AnalysisFindings): { text: string; suggestions: string[] } {
	if (found.kind === "image") return { text: `${name} is in. I can place it wherever you like.`, suggestions: [] };
	const facts = [
		found.words > 0 && `${found.words} words${found.language ? ` (${found.language.toUpperCase()})` : ""}`,
		found.shots > 1 && `${found.shots} shots`,
		found.dead_air >= 1 && `${Math.round(found.dead_air)}s of dead air`,
		found.fillers > 0 && `${found.fillers} filler word${found.fillers === 1 ? "" : "s"}`,
		found.tempo_bpm && `${Math.round(found.tempo_bpm)} bpm`,
	].filter(Boolean);
	const lines = [`I've gone through ${name} (${clock(found.duration)})${facts.length ? `: ${facts.join(", ")}.` : "."}`];
	if (found.summary) lines.push("", found.summary);
	if (found.topics.length) lines.push(`Topics: ${found.topics.join(" · ")}`);
	if (found.kind === "video" && found.words === 0) lines.push("Nobody speaks in it, so I'll cut it by the picture.");
	if (found.moments.length) {
		lines.push("", "Best moments:", ...found.moments.map((moment) => `• ${clock(moment.t0)}  ${moment.text}`));
	}
	if (found.problems.length) lines.push("", ...found.problems.map((problem) => `Heads-up: ${problem}`));
	if (found.suggestions.length) lines.push("", "What should I do with it?");
	return { text: lines.join("\n"), suggestions: found.suggestions };
}
