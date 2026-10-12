/**
 * The studio's AI conversation: prompts go to /editor/projects/{id}/turns with the selection and
 * playhead, and any change the AI makes is pulled straight onto the timeline.
 *
 * Plans come back as cards. Approving one follows its live event stream: every applied op is
 * pulled onto the timeline at once, with a marker where the agent is working; any edit made by
 * hand while it runs pauses it (resume re-solves the remaining steps against the new timeline).
 * Kept per project in memory, so switching tabs doesn't lose the chat.
 */

import { create } from "zustand";
import { EditorCore } from "@opencut/core";
import { editorApi, type PlanCard, type PlanPatch, plansApi, type TurnChoice, type TurnKind } from "@/lib/api";
import { toFrame } from "./bridge";
import { clearAiMarkers, showCursor, showGhost } from "./ghost";
import { getCurrentSync } from "./save-status";

export interface AiMessage {
	id: string;
	role: "user" | "ai";
	text: string;
	kind?: TurnKind | "error";
	choices?: TurnChoice[];
	options?: string[];
	// Whole prompts offered as one-click next steps.
	suggestions?: string[];
	planId?: string;
	// The prompt a choice chip re-sends with that item selected.
	prompt?: string;
	undoStepId?: string | null;
	undone?: boolean;
}

interface AiState {
	byProject: Record<string, AiMessage[]>;
	plans: Record<string, PlanCard>;
	busy: boolean;
	/** ``shown``: the prompt is already in the chat (it waited for the files to be understood). */
	send: (prompt: string, selection?: string[], shown?: boolean) => Promise<void>;
	/** Put a message from the AI in the chat without a model call, after the user's line if given. */
	note: (projectId: string, userText: string | null, text: string, suggestions?: string[]) => void;
	undo: (messageId: string) => Promise<void>;
	approve: (planId: string) => Promise<void>;
	reject: (planId: string) => Promise<void>;
	editPlan: (planId: string, patch: PlanPatch) => Promise<void>;
	control: (planId: string, action: "pause" | "resume" | "stop") => Promise<void>;
	alternative: (planId: string) => Promise<void>;
	undoStep: (planId: string, undoStepId: string) => Promise<void>;
}

const RECENT_TURNS = 3;
const ACTIVE = new Set(["approved", "running"]);
let nextId = 0;
const id = () => `m${++nextId}`;
const errorText = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

// The plan being followed, its stream, and the hook that pauses it on a manual edit.
let following: { planId: string; abort: AbortController; stopListening: () => void } | null = null;

export const useAiStore = create<AiState>((set, get) => {
	const messagesOf = (projectId: string) => get().byProject[projectId] ?? [];
	const push = (projectId: string, message: AiMessage) =>
		set((state) => ({ byProject: { ...state.byProject, [projectId]: [...messagesOf(projectId), message] } }));
	const patchMessage = (projectId: string, messageId: string, change: Partial<AiMessage>) =>
		set((state) => ({
			byProject: {
				...state.byProject,
				[projectId]: messagesOf(projectId).map((m) => (m.id === messageId ? { ...m, ...change } : m)),
			},
		}));
	const putPlan = (card: PlanCard) => set((state) => ({ plans: { ...state.plans, [card.id]: card } }));
	const fail = (projectId: string, error: unknown, fallback: string) =>
		push(projectId, { id: id(), role: "ai", kind: "error", text: errorText(error, fallback) });

	/** Run ``work`` with the busy flag, reporting a failure in the chat. */
	const guarded = async (fallback: string, work: (projectId: string) => Promise<void>) => {
		const sync = getCurrentSync();
		if (!sync || get().busy) return;
		set({ busy: true });
		try {
			await work(sync.getProjectId());
		} catch (error) {
			fail(sync.getProjectId(), error, fallback);
		} finally {
			set({ busy: false });
		}
	};

	const showPlan = (card: PlanCard) => {
		putPlan(card);
		if (card.status === "proposed") showGhost(card.ghost, card.fps);
	};

	const follow = (planId: string) => {
		const sync = getCurrentSync();
		if (!sync) return;
		following?.abort.abort();
		following?.stopListening();
		const abort = new AbortController();
		// 11.5.1: any edit made by hand while the plan runs pauses it.
		const stopListening = sync.onLocalEdit(() => {
			const card = get().plans[planId];
			if (card && ACTIVE.has(card.status)) void plansApi.pause(planId).then(putPlan).catch(() => undefined);
		});
		following = { planId, abort, stopListening };
		void plansApi
			.stream(
				planId,
				(event) => {
					if (event.event === "plan.updated") putPlan(event.data);
					if (event.event === "op.applied") {
						void sync.refresh().then(() => event.data.cursor && showCursor(event.data.cursor.items));
					}
					if (event.event === "done") void sync.refresh().then(clearAiMarkers);
				},
				abort.signal,
			)
			.catch(() => undefined)
			.finally(() => {
				stopListening();
				if (following?.planId === planId) following = null;
			});
	};

	return {
		byProject: {},
		plans: {},
		busy: false,

		note(projectId, userText, text, suggestions) {
			if (userText) push(projectId, { id: id(), role: "user", text: userText });
			push(projectId, { id: id(), role: "ai", text, suggestions });
		},

		async send(prompt, selection, shown = false) {
			const text = prompt.trim();
			if (!text) return;
			await guarded("Something went wrong. Try again.", async (projectId) => {
				const sync = getCurrentSync()!;
				const said = messagesOf(projectId).filter((m) => m.role === "user").map((m) => m.text);
				const earlier = (shown ? said.slice(0, -1) : said).slice(-RECENT_TURNS);
				if (!shown) push(projectId, { id: id(), role: "user", text });
				// The AI must see every edit made by hand so far.
				await sync.flush();
				const editor = EditorCore.getInstance();
				const result = await editorApi.turn(projectId, {
					prompt: text,
					selection: selection ?? editor.selection.getSelectedElements().map((ref) => ref.elementId),
					playhead: Math.max(0, toFrame(editor.playback.getCurrentTime(), sync.getFps())),
					recent_turns: earlier,
				});
				if (result.version !== null) await sync.refresh();
				if (result.plan) showPlan(result.plan);
				push(projectId, {
					id: id(), role: "ai", text: result.message, kind: result.kind, choices: result.choices,
					options: result.options, planId: result.plan?.id, prompt: text, undoStepId: result.undo_step_id,
				});
			});
		},

		async undo(messageId) {
			await guarded("Couldn't undo that.", async (projectId) => {
				const sync = getCurrentSync()!;
				const message = messagesOf(projectId).find((m) => m.id === messageId);
				if (!message?.undoStepId || message.undone) return;
				await sync.flush();
				await editorApi.undoStep(projectId, message.undoStepId);
				await sync.refresh();
				patchMessage(projectId, messageId, { undone: true });
			});
		},

		async approve(planId) {
			await guarded("Couldn't start the plan.", async () => {
				await getCurrentSync()!.flush();
				clearAiMarkers();
				putPlan(await plansApi.approve(planId));
				follow(planId);
			});
		},

		async reject(planId) {
			await guarded("Couldn't reject the plan.", async () => {
				clearAiMarkers();
				putPlan(await plansApi.reject(planId));
			});
		},

		async editPlan(planId, patch) {
			await guarded("Couldn't change the plan.", async () => putPlan(await plansApi.edit(planId, patch)));
		},

		async control(planId, action) {
			await guarded(`Couldn't ${action} the plan.`, async () => {
				putPlan(await plansApi[action](planId));
				if (action === "resume") follow(planId);
				if (action === "stop") {
					await getCurrentSync()!.refresh();
					clearAiMarkers();
				}
			});
		},

		async alternative(planId) {
			await guarded("There's no other version any more.", async (projectId) => {
				const card = await plansApi.alternative(planId);
				showPlan(card);
				push(projectId, { id: id(), role: "ai", kind: "plan", text: card.summary, planId: card.id });
			});
		},

		async undoStep(planId, undoStepId) {
			await guarded("Couldn't undo that step.", async (projectId) => {
				const sync = getCurrentSync()!;
				await sync.flush();
				await editorApi.undoStep(projectId, undoStepId);
				await sync.refresh();
				putPlan(await plansApi.get(planId));
			});
		},
	};
});
