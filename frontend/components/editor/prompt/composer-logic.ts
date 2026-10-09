/**
 * Pure rules behind the docked composer (07 §6.1, 02-editor §3.1): what blocks sending, the hint,
 * the line under the box after a failed send, queue edits as API calls, and the phone line's live
 * step. Import-free apart from types, so `node --test` can check it.
 */
import type { QueuedPrompt } from '@/components/ui/PromptQueue';
import type { RunEstimate, RunMode } from '@/lib/api/editor/types';
import type { Turn } from '@/lib/editor/run-store';

export const MODES: ReadonlyArray<RunMode> = ['edit', 'ask', 'plan'];

/** ⇧Tab in the text field cycles Edit → Ask → Plan. */
export const nextMode = (mode: RunMode): RunMode => MODES[(MODES.indexOf(mode) + 1) % MODES.length];

/* ───────────── what blocks sending ───────────── */

export interface BlockInput {
  /** False during the server render and before the client takes over. */
  hydrated: boolean;
  /** A project id and a loaded document. */
  projectReady: boolean;
  online: boolean;
  /** Viewing an earlier version. */
  readOnly: boolean;
  /** The estimate says the balance doesn't cover this prompt. */
  shortOfCredits: boolean;
}

/**
 * `disabled` turns the whole box off (text can't change); otherwise `reason` only stops Send and
 * the text stays editable (offline, not enough credits).
 */
export type Block = { disabled: true; reason?: string } | { disabled: false; reason: string };

export function composerBlock({ hydrated, projectReady, online, readOnly, shortOfCredits }: BlockInput): Block | null {
  if (!hydrated) return { disabled: true };
  if (!projectReady) return { disabled: true, reason: 'Opening the project' };
  if (readOnly) return { disabled: true, reason: 'Viewing an earlier version. Go back to the latest to edit.' };
  if (!online) return { disabled: false, reason: "You're offline. Your text is kept." };
  if (shortOfCredits) return { disabled: false, reason: 'Not enough credits for this edit' };
  return null;
}

/* ───────────── estimate and hint ───────────── */

/** Only real prompts are estimated: not empty, not a `/command` being typed. */
export const wantsEstimate = (prompt: string): boolean => {
  const text = prompt.trim();
  return text.length > 0 && !text.startsWith('/');
};

export const isShortOfCredits = (estimate: RunEstimate | undefined): boolean =>
  estimate !== undefined && !estimate.free && estimate.balance !== undefined && estimate.credits > estimate.balance;

const credits = (n: number) => `${n} credit${n === 1 ? '' : 's'}`;

/** The hint slot: "2 waiting" while prompts queue behind a run, else the estimate when one exists. */
export function composerHint(estimate: RunEstimate | undefined, queueCount: number): string | undefined {
  if (queueCount > 0) return `${queueCount} waiting`;
  if (!estimate) return undefined;
  return estimate.free ? 'Free' : `≈ ${credits(estimate.credits)}`;
}

/** "Needs 12 credits; you have 6." under the box when the balance is short. */
export const shortOfCreditsText = (estimate: RunEstimate): string =>
  `Needs ${credits(estimate.credits)}; you have ${estimate.balance ?? 0}.`;

/* ───────────── failed send ───────────── */

export type SendIssueKind = 'offline' | 'credits' | 'other';

export interface SendIssue {
  kind: SendIssueKind;
  text: string;
}

/** What went wrong with `POST /runs`, in the words the line under the box uses. */
export function sendIssue(error: { status?: number; code?: string; message?: string }, describe: (code?: string, message?: string) => string): SendIssue {
  if (error.status === 0 || error.code === 'NETWORK' || error.code === 'TIMEOUT') return { kind: 'offline', text: 'Not sent. Check your connection.' };
  if (error.code === 'INSUFFICIENT_CREDITS') return { kind: 'credits', text: "Not sent. You don't have enough credits for this edit." };
  return { kind: 'other', text: `Not sent. ${describe(error.code, error.message)}` };
}

/* ───────────── queue ───────────── */

export interface QueueChange {
  removed: string[];
  edited: { id: string; prompt: string }[];
  /** 1-based `queue_position`, for items whose place changed. */
  moved: { id: string; position: number }[];
}

/** Turns PromptQueue's whole-list `onChange` into the `PATCH`/`DELETE /runs/{id}` calls it implies. */
export function diffQueue(before: ReadonlyArray<QueuedPrompt>, after: ReadonlyArray<QueuedPrompt>): QueueChange {
  const kept = new Map(after.map((item, index) => [item.id, { item, index }]));
  const removed = before.filter((item) => !kept.has(item.id)).map((item) => item.id);
  const remaining = before.filter((item) => kept.has(item.id));
  const edited: QueueChange['edited'] = [];
  const moved: QueueChange['moved'] = [];
  remaining.forEach((item, index) => {
    const next = kept.get(item.id)!;
    if (next.item.prompt !== item.prompt) edited.push({ id: item.id, prompt: next.item.prompt });
    if (next.index !== index) moved.push({ id: item.id, position: next.index + 1 });
  });
  return { removed, edited, moved };
}

/** Queued turns as PromptQueue items, with prompt edits the server hasn't echoed yet laid over them. */
export function queueItems(queue: ReadonlyArray<Turn>, edits: Readonly<Record<string, string>>): QueuedPrompt[] {
  return queue.map((turn) => ({ id: turn.id, prompt: edits[turn.id] ?? turn.prompt, chips: turn.chips }));
}

/* ───────────── live step (phone line) ───────────── */

const STATUS_LINE: Partial<Record<Turn['status'], string>> = {
  sending: 'Reading your request',
  acknowledged: 'Reading your request',
  planning: 'Planning the edit',
  awaiting_input: 'Waiting for your answer',
  paused: 'Paused · needs you',
  stopping: 'Stopping',
  checking: 'Checking the result',
};

/** One line for the active run: "Trimming silences · step 2 of 4 · 9 of 14". */
export function liveStep(turn: Turn): string {
  if (turn.stopping) return 'Stopping';
  const fixed = STATUS_LINE[turn.status];
  if (fixed) return fixed;
  const index = turn.steps.findIndex((step) => step.status === 'active');
  if (index < 0) return 'Working on it';
  const step = turn.steps[index];
  return [step.label, `step ${index + 1} of ${turn.steps.length}`, step.progress].filter(Boolean).join(' · ');
}

/** Docked placeholder (07 §6.1): "What next?" right after a result when nothing is selected. */
export function composerPlaceholder(lastTurn: Turn | undefined, chipCount: number): string | undefined {
  if (chipCount > 0 || !lastTurn) return undefined;
  return lastTurn.status === 'succeeded' || lastTurn.status === 'partial' ? 'What next?' : undefined;
}
