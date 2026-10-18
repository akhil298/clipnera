/**
 * The studio's AI conversation: prompts go to the studio agent (/editor/projects/{id}/agent) with
 * the selection, the playhead and the conversation so far. It streams what it does: each tool call
 * shows as a step, each edit is pulled straight onto the timeline (with its own Undo), and it moves
 * the playhead, selects and plays ranges in the studio (agent-ui.ts). Stop ends the turn at once.
 *
 * Plans come back as cards. Approving one follows its live event stream: every applied op is
 * pulled onto the timeline at once, with a marker where the agent is working; any edit made by
 * hand while it runs pauses it (resume re-solves the remaining steps against the new timeline).
 * Kept per project in memory, so switching tabs doesn't lose the chat.
 */

import { create } from "zustand";
import { EditorCore } from "@opencut/core";
import {
	type AgentEvent,
	type AgentExchange,
	agentApi,
	type AgentTodo,
	editorApi,
	type PlanCard,
	type PlanPatch,
	plansApi,
	type RenderStatus,
	type TurnChoice,
	type TurnKind,
} from "@/lib/api";
import { useAiPick } from "@/lib/editor/aiPick";
import { actOn } from "./agent-ui";
import { toFrame } from "./bridge";
import { clearAiMarkers, showCursor, showGhost } from "./ghost";
import { getCurrentSync } from "./save-status";

/** One tool call of an agent turn, as the chat shows it. */
export interface AgentStep {
	id: string;
	label: string;
	state: "running" | "done" | "failed";
	error?: string | null;
}

/** One change the agent made: an undoable step of its own. */
export interface AgentEditRow {
	label: string;
	undoStepId: string;
	undone: boolean;
}

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
	// An agent turn: its steps, edits and to-do list, live while ``working``.
	steps?: AgentStep[];
	edits?: AgentEditRow[];
	todos?: AgentTodo[];
	render?: RenderStatus;
	working?: boolean;
}

interface AiState {
	byProject: Record<string, AiMessage[]>;
	plans: Record<string, PlanCard>;
	busy: boolean;
	// Auto mode: the AI never asks and runs its plans without waiting for approval.
	auto: boolean;
	setAuto: (auto: boolean) => void;
	/** ``shown``: the prompt is already in the chat (it waited for the files to be understood). */
	send: (prompt: string, selection?: string[], shown?: boolean) => Promise<void>;
	/** Put a message from the AI in the chat without a model call, after the user's line if given. */
	note: (projectId: string, userText: string | null, text: string, suggestions?: string[]) => void;
	undo: (messageId: string) => Promise<void>;
	/** Undo some of an agent turn's edits (all of them when ``undoStepIds`` is left out), newest first. */
	undoEdits: (messageId: string, undoStepIds?: string[]) => Promise<void>;
	/** Stop the agent's turn now; what it already changed stays. */
	stop: () => void;
	approve: (planId: string) => Promise<void>;
	reject: (planId: string) => Promise<void>;
	editPlan: (planId: string, patch: PlanPatch) => Promise<void>;
	control: (planId: string, action: "pause" | "resume" | "stop") => Promise<void>;
	alternative: (planId: string) => Promise<void>;
	undoStep: (planId: string, undoStepId: string) => Promise<void>;
}

// Earlier exchanges sent with a prompt (backend AgentRequest.history), and how long each part may be.
const HISTORY = 6;
const PROMPT_CHARS = 2000;
const REPLY_CHARS = 4000;
const AUTO_KEY = "clipnera-ai-auto";

/** Auto mode is on unless this browser turned it off. */
function savedAuto(): boolean {
	try {
		return localStorage.getItem(AUTO_KEY) !== "false";
	} catch {
		return true;
	}
}
const ACTIVE = new Set(["approved", "running"]);
let nextId = 0;
const id = () => `m${++nextId}`;
const errorText = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

const QUESTIONS: ReadonlySet<AiMessage["kind"]> = new Set(["clarify", "choices"]);

/** How many questions the AI has asked since it last did or answered something. */
function questionsInARow(messages: AiMessage[]): number {
	let count = 0;
	for (const message of [...messages].reverse()) {
		// The user's lines, and notes about files, sit between questions without ending the run.
		if (message.role === "user" || !message.kind) continue;
		if (!QUESTIONS.has(message.kind)) break;
		count += 1;
	}
	return count;
}

/** The conversation as prompt/reply pairs: each user line with what the AI said after it. */
function exchanges(messages: AiMessage[]): AgentExchange[] {
	const pairs: AgentExchange[] = [];
	for (const message of messages) {
		if (message.role === "user") pairs.push({ prompt: message.text, reply: "" });
		else if (pairs.length && message.text && message.kind !== "error") {
			const last = pairs[pairs.length - 1];
			last.reply = last.reply ? `${last.reply}\n${message.text}` : message.text;
		}
	}
	return pairs.slice(-HISTORY).map((pair) => ({
		prompt: pair.prompt.slice(0, PROMPT_CHARS),
		reply: pair.reply.slice(0, REPLY_CHARS),
	}));
}

// The agent turn in progress, to stop it.
let running: AbortController | null = null;

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
		auto: savedAuto(),

		setAuto(auto) {
			set({ auto });
			try {
				localStorage.setItem(AUTO_KEY, String(auto));
			} catch {
				// Private windows may refuse storage; the switch still works for this visit.
			}
		},

		note(projectId, userText, text, suggestions) {
			if (userText) push(projectId, { id: id(), role: "user", text: userText });
			push(projectId, { id: id(), role: "ai", text, suggestions });
		},

		async send(prompt, selection, shown = false) {
			const text = prompt.trim();
			if (!text) return;
			await guarded("Something went wrong. Try again.", async (projectId) => {
				const sync = getCurrentSync()!;
				const earlier = exchanges(messagesOf(projectId));
				// A prompt already in the chat is the last exchange: it is this one, not history.
				const history = shown && earlier.at(-1)?.prompt === text.slice(0, PROMPT_CHARS) ? earlier.slice(0, -1) : earlier;
				if (!shown) push(projectId, { id: id(), role: "user", text });
				// The AI must see every edit made by hand so far.
				await sync.flush();
				const editor = EditorCore.getInstance();
				const turnId = id();
				push(projectId, { id: turnId, role: "ai", text: "", kind: "answer", prompt: text, steps: [], edits: [], working: true });
				const turn = () => messagesOf(projectId).find((m) => m.id === turnId)!;
				const patch = (change: Partial<AiMessage>) => patchMessage(projectId, turnId, change);
				const texts: string[] = [];
				const say = (line: string) => {
					texts.push(line.trim());
					patch({ text: texts.filter(Boolean).join("\n\n") });
				};
				// Edits arrive faster than a refresh: pull them onto the timeline one after another.
				let pulled = Promise.resolve();
				const pull = () => {
					pulled = pulled.then(() => sync.refresh()).catch(() => undefined);
				};

				const onEvent = ({ event, data }: AgentEvent) => {
					if (event === "text") say(data.text);
					if (event === "tool") patch({ steps: [...(turn().steps ?? []), { id: data.id, label: data.label, state: "running" }] });
					if (event === "tool_done") {
						patch({ steps: turn().steps?.map((step) => step.id === data.id && step.state === "running"
							? { ...step, state: data.ok ? "done" : "failed", error: data.error } : step) });
					}
					if (event === "edit") {
						patch({ edits: [...(turn().edits ?? []), { label: data.label, undoStepId: data.undo_step_id, undone: false }] });
						pull();
					}
					if (event === "undone") {
						patch({ edits: turn().edits?.map((edit) => (edit.undoStepId === data.undo_step_id ? { ...edit, undone: true } : edit)) });
						pull();
					}
					if (event === "ui") actOn(data, sync.getFps());
					if (event === "todos") patch({ todos: data.items });
					if (event === "render") patch({ render: data });
					if (event === "ask") {
						push(projectId, { id: id(), role: "ai", kind: "clarify", text: data.question, options: data.options, prompt: text });
					}
					if (event === "plan") {
						showPlan(data);
						// Auto mode started the plan already: watch it run.
						if (ACTIVE.has(data.status)) follow(data.id);
						push(projectId, { id: id(), role: "ai", kind: "plan", text: data.summary, planId: data.id, prompt: text });
					}
					if (event === "result") {
						// Undo, redo, split and delete: done without a model.
						if (data.version !== null) pull();
						patch({ text: data.message, kind: data.kind, choices: data.choices, options: data.options, undoStepId: data.undo_step_id });
					}
					if (event === "done" && data.message) say(data.message);
					if (event === "error") patch({ kind: "error", text: data.message });
				};

				const abort = new AbortController();
				running = abort;
				try {
					await agentApi.run(projectId, {
						prompt: text,
						selection: selection ?? editor.selection.getSelectedElements().map((ref) => ref.elementId),
						playhead: Math.max(0, toFrame(editor.playback.getCurrentTime(), sync.getFps())),
						history,
						questions_asked: questionsInARow(messagesOf(projectId)),
						auto: get().auto,
						model: useAiPick.getState().model,
						effort: useAiPick.getState().effort,
					}, onEvent, abort.signal);
				} catch (error) {
					if (!abort.signal.aborted) throw error;
					say("Stopped. What I'd already changed is still there.");
				} finally {
					running = null;
					await pulled;
					patch({ working: false, steps: turn().steps?.map((step) => (step.state === "running" ? { ...step, state: "failed" } : step)) });
				}
			});
		},

		stop() {
			running?.abort();
		},

		async undoEdits(messageId, undoStepIds) {
			await guarded("Couldn't undo that.", async (projectId) => {
				const sync = getCurrentSync()!;
				const edits = messagesOf(projectId).find((m) => m.id === messageId)?.edits ?? [];
				const chosen = edits.filter((edit) => !edit.undone && (!undoStepIds || undoStepIds.includes(edit.undoStepId)));
				if (!chosen.length) return;
				await sync.flush();
				const undone = new Set<string>();
				try {
					for (const edit of [...chosen].reverse()) {
						await editorApi.undoStep(projectId, edit.undoStepId);
						undone.add(edit.undoStepId);
					}
				} finally {
					await sync.refresh();
					patchMessage(projectId, messageId, {
						edits: edits.map((edit) => (undone.has(edit.undoStepId) ? { ...edit, undone: true } : edit)),
					});
				}
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
