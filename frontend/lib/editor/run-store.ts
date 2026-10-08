/**
 * The conversation's state: one turn per prompt, built from run events (docs/revamp/architecture/
 * events.md §3) as 02-editor.md §3.2 lays them out. `reduceRun` is pure and holds every rule:
 * de-duplication and gap buffering by `seq` (events.md §7.3), locks per item, AI-change markers,
 * and the local moments before the server answers (sending, a picked choice, Stop).
 *
 * Wiring: lib/realtime/handlers/runs.ts (E4a) dispatches `{kind:'event'}` and, for
 * `run.operation.applied`, also calls the doc store's `applyRemote`. Until the stream exists
 * (EB-1), lib/editor/dev/simulator.ts dispatches the same events.
 */
import { useStore } from 'zustand';
import { createStore, type StoreApi } from 'zustand/vanilla';

import type { PromptContext } from '@/components/ui/ContextChip';
import {
  EPHEMERAL_RUN_EVENTS,
  TERMINAL_RUN_STATUSES,
  type Citation,
  type Credits,
  type ErrorObject,
  type FindingItem,
  type PlanStepOutline,
  type Run,
  type RunEvent,
  type RunEventOf,
  type RunMode,
  type RunQuestion,
  type RunStatus,
  type Suggestion,
} from '@/lib/api/editor/types';

import { contextFromWire } from './selection';

/* ───────────── state ───────────── */

/** Same shape as `RunStep` in components/ui/StepList, so a turn's steps render as they are. */
export interface TurnStep {
  id: string;
  label: string;
  status: 'queued' | 'active' | 'done' | 'failed' | 'skipped';
  detail?: string;
  progress?: string;
}

/** `sending`: before the server answered POST /runs. `send_failed`: it never arrived (text is kept). */
export type TurnStatus = RunStatus | 'sending' | 'send_failed';

export interface Turn {
  /** Stable client key; the server id is `runId`. */
  id: string;
  runId: string | null;
  prompt: string;
  chips: PromptContext[];
  mode: RunMode;
  status: TurnStatus;
  queuePosition: number | null;
  /** ms since epoch, when known. */
  startedAt?: number;
  endedAt?: number;
  /** Streamed plan text, then the final plan sentences. */
  planText: string;
  plan?: { sentences: string[]; steps: PlanStepOutline[]; targets?: { clip_ids?: string[]; ranges?: [number, number][] }; needsApproval: boolean };
  credits?: Credits;
  steps: TurnStep[];
  checking: boolean;
  checkFindings: { severity: 'info' | 'warn'; text: string }[];
  /** Source strip cards (EB-8). */
  sources: FindingItem[];
  question?: RunQuestion & { chosenId?: string; skipped?: boolean; by?: 'user' | 'timeout' };
  pause?: RunEventOf<'run.paused'>['data'] & { decided?: 'continue' | 'finish' | 'add_credits' };
  stopping: boolean;
  /** Ask mode answer as it streams (`role: answer`). */
  answerText: string;
  /** Result summary as it streams (`role: summary`). */
  summaryText: string;
  /** EB-7; merged by id from plan, message and result. */
  citations: Citation[];
  result?: RunEventOf<'run.result'>['data'];
  failure?: { error: ErrorObject; version: { id: string; name: string } | null; suggestion?: Suggestion };
  cancelled?: { by: 'user' | 'system'; while: 'queued' | 'running'; changed: boolean };
  sendError?: { code: string; message: string };
  /** Revisions this run committed, in order. */
  revisions: number[];
  /** Items its operations touched. */
  touched: string[];
  undone: boolean;
  retryOf?: string;
}

/** The AI-change marker on a timeline item (02-editor §5.1). */
export interface Marker {
  turnId: string;
  runId: string;
  revision: number;
}

export interface RunState {
  /** Oldest first. */
  turns: Turn[];
  /** Highest durable seq applied per run. */
  lastSeq: Record<string, number>;
  /** Durable events that arrived ahead of a gap, per run. */
  buffered: Record<string, RunEvent[]>;
  /** Runs with a gap: fetch `GET /runs/{id}/events?after_seq=<value>` and dispatch the result. */
  backfill: Record<string, number>;
  /** Item id → run holding it. */
  locks: Record<string, string>;
  markers: Record<string, Marker>;
}

export const INITIAL_RUN_STATE: RunState = { turns: [], lastSeq: {}, buffered: {}, backfill: {}, locks: {}, markers: {} };

/* ───────────── actions ───────────── */

export type RunAction =
  | { kind: 'send'; turnId: string; prompt: string; chips: PromptContext[]; mode: RunMode; at?: number; retryOf?: string }
  | { kind: 'send.failed'; turnId: string; error: { code: string; message: string } }
  /** POST /runs (or /retry) answered with the Run. */
  | { kind: 'bind'; turnId: string; run: Run }
  /** Run snapshots from GET runs / activity (older turns, or a run that finished while away). */
  | { kind: 'hydrate'; runs: Run[] }
  | { kind: 'event'; event: RunEvent }
  /** Optimistic: shows the pick at once; `run.answered` confirms. */
  | { kind: 'answer'; runId: string; choiceId: string | 'skip' }
  | { kind: 'decide'; runId: string; decision: 'continue' | 'finish' | 'add_credits' }
  | { kind: 'stop'; runId: string }
  | { kind: 'undone'; turnId: string; undone: boolean }
  /** A hand edit on these items clears their markers; no ids clears all. */
  | { kind: 'markers.clear'; itemIds?: string[] }
  /** A queued prompt removed (DELETE /runs/{id}), or a failed send discarded. */
  | { kind: 'remove'; turnId: string }
  | { kind: 'reset' };

/* ───────────── helpers ───────────── */

const STOPPED = 'Stopped before this step';

const isTerminal = (status: TurnStatus) => TERMINAL_RUN_STATUSES.has(status as RunStatus);

function blankTurn(id: string, runId: string | null, prompt: string, chips: PromptContext[], mode: RunMode, status: TurnStatus): Turn {
  return {
    id,
    runId,
    prompt,
    chips,
    mode,
    status,
    queuePosition: null,
    planText: '',
    steps: [],
    checking: false,
    checkFindings: [],
    sources: [],
    stopping: false,
    answerText: '',
    summaryText: '',
    citations: [],
    revisions: [],
    touched: [],
    undone: false,
  };
}

const SNAPSHOT_STEP: Record<string, TurnStep['status']> = {
  pending: 'queued',
  running: 'active',
  completed: 'done',
  failed: 'failed',
  skipped: 'skipped',
};

const parseTime = (iso?: string | null) => (iso ? Date.parse(iso) : undefined);

/** A turn rebuilt from a Run snapshot (EB-3 `GET /runs`, EB-6 activity). */
export function turnFromRun(run: Run, id = run.id): Turn {
  const turn = blankTurn(id, run.id, run.prompt, (run.chips ?? []).map(contextFromWire), run.mode, run.status);
  const summary = run.summary;
  return {
    ...turn,
    queuePosition: run.queue_position ?? null,
    startedAt: parseTime(run.started_at ?? run.created_at),
    endedAt: parseTime(run.finished_at),
    credits: run.credits,
    planText: run.plan?.sentences.join(' ') ?? '',
    plan: run.plan ? { sentences: run.plan.sentences, steps: run.plan.steps.map(({ id: stepId, label }) => ({ id: stepId, label })), needsApproval: false } : undefined,
    steps: (run.plan?.steps ?? []).map((step) => ({ id: step.id, label: step.label, status: SNAPSHOT_STEP[step.status] ?? 'queued', detail: step.summary ?? undefined })),
    question: run.question ?? undefined,
    answerText: summary?.answer ?? '',
    result:
      run.status === 'succeeded' || run.status === 'partial'
        ? {
            status: run.status,
            version: run.version ? { id: run.version.id, name: run.version.name, result_revision: run.version.result_revision } : null,
            summary: { done: summary?.done ?? [], not_done: summary?.not_done ?? [] },
            answer: summary?.answer,
            suggestions: summary?.suggestions ?? [],
            credits: run.credits,
            duration_ms: 0,
          }
        : undefined,
    failure: run.status === 'failed' && run.error ? { error: run.error, version: run.version ? { id: run.version.id, name: run.version.name } : null } : undefined,
    cancelled: run.status === 'cancelled' ? { by: 'user', while: run.started_at ? 'running' : 'queued', changed: Boolean(run.version) } : undefined,
  };
}

function setStep(steps: TurnStep[], id: string, patch: Partial<TurnStep>): TurnStep[] {
  return steps.map((step) => (step.id === id ? { ...step, ...patch } : step));
}

function mergeCitations(current: Citation[], incoming?: Citation[]): Citation[] {
  if (!incoming?.length) return current;
  const byId = new Map(current.map((c) => [c.id, c]));
  for (const citation of incoming) byId.set(citation.id, citation);
  return Array.from(byId.values());
}

const skipQueued = (steps: TurnStep[], detail?: string) =>
  steps.map((step) => (step.status === 'queued' ? { ...step, status: 'skipped' as const, detail } : step));

function releaseRun(locks: Record<string, string>, runId: string): Record<string, string> {
  return Object.fromEntries(Object.entries(locks).filter(([, holder]) => holder !== runId));
}

function patchTurn(state: RunState, turnId: string, patch: (turn: Turn) => Turn): RunState {
  return { ...state, turns: state.turns.map((turn) => (turn.id === turnId ? patch(turn) : turn)) };
}

/* ───────────── one event onto one turn ───────────── */

function applyToTurn(turn: Turn, event: RunEvent): Turn {
  const at = parseTime(event.ts);
  switch (event.type) {
    case 'run.queued':
      return { ...turn, status: 'queued', queuePosition: event.data.queue_position, prompt: turn.prompt || event.data.prompt_preview };
    case 'run.queue.updated':
      return { ...turn, queuePosition: event.data.queue_position };
    case 'run.acknowledged':
      return {
        ...turn,
        status: 'acknowledged',
        queuePosition: null,
        mode: event.data.mode,
        credits: event.data.credits,
        startedAt: turn.startedAt ?? at,
        chips: turn.chips.length ? turn.chips : event.data.chips.map(contextFromWire),
      };
    case 'run.plan.delta':
      return { ...turn, status: turn.status === 'acknowledged' ? 'planning' : turn.status, planText: turn.planText + event.data.text };
    case 'run.plan':
      return {
        ...turn,
        status: turn.status === 'acknowledged' ? 'planning' : turn.status,
        planText: event.data.sentences.join(' '),
        plan: { sentences: event.data.sentences, steps: event.data.steps, targets: event.data.targets, needsApproval: event.data.needs_approval },
        credits: event.data.credits,
        citations: mergeCitations(turn.citations, event.data.citations),
        steps: turn.mode === 'plan' ? [] : event.data.steps.map((step) => turn.steps.find((s) => s.id === step.id) ?? { id: step.id, label: step.label, status: 'queued' }),
      };
    case 'run.message.delta':
      return {
        ...turn,
        answerText: event.data.role === 'answer' ? turn.answerText + event.data.text : turn.answerText,
        summaryText: event.data.role === 'summary' ? turn.summaryText + event.data.text : turn.summaryText,
        citations: mergeCitations(turn.citations, event.data.citations),
      };
    case 'run.finding': {
      const known = new Set(turn.sources.map((s) => s.id));
      return { ...turn, sources: [...turn.sources, ...event.data.items.filter((item) => !known.has(item.id))] };
    }
    case 'run.question': {
      const { allow_skip: _skip, ...question } = event.data;
      return { ...turn, status: 'awaiting_input', question };
    }
    case 'run.answered':
      return {
        ...turn,
        status: turn.steps.some((step) => step.status === 'active') ? 'executing' : 'planning',
        question: turn.question && {
          ...turn.question,
          chosenId: event.data.skipped ? undefined : event.data.choice_id,
          skipped: event.data.skipped,
          by: event.data.by,
        },
      };
    case 'run.step.started': {
      const { step_id, label } = event.data;
      const known = turn.steps.some((step) => step.id === step_id);
      const steps = known
        ? setStep(turn.steps, step_id, { label, status: 'active', detail: undefined, progress: undefined })
        : [...turn.steps, { id: step_id, label, status: 'active' as const }];
      return { ...turn, status: turn.stopping ? 'stopping' : 'executing', steps };
    }
    case 'run.step.progress': {
      const { done, total, percent, label } = event.data;
      // Real numbers only: a percentage shows only when the server sends one.
      const progress = label ?? (done !== undefined && total !== undefined ? `${done} of ${total}` : percent !== undefined ? `${Math.round(percent)}%` : undefined);
      return { ...turn, steps: setStep(turn.steps, event.data.step_id, { progress }) };
    }
    case 'run.step.completed':
      return { ...turn, steps: setStep(turn.steps, event.data.step_id, { status: 'done', label: event.data.label, detail: event.data.summary, progress: undefined }) };
    case 'run.step.failed':
      return {
        ...turn,
        steps: setStep(
          turn.steps,
          event.data.step_id,
          event.data.will_retry
            ? { status: 'active', progress: 'Trying again', detail: event.data.error.message }
            : { status: 'failed', progress: undefined, detail: event.data.error.message },
        ),
      };
    case 'run.operation.applied':
      if (turn.revisions.includes(event.data.revision)) return turn;
      return {
        ...turn,
        revisions: [...turn.revisions, event.data.revision],
        touched: Array.from(new Set([...turn.touched, ...event.data.item_ids])),
      };
    case 'run.check.started':
      return {
        ...turn,
        status: 'checking',
        checking: true,
        steps: turn.steps.some((s) => s.id === 'check') ? turn.steps : [...turn.steps, { id: 'check', label: 'Checking the result', status: 'active' }],
      };
    case 'run.check.completed':
      return {
        ...turn,
        checking: false,
        checkFindings: event.data.findings,
        steps: setStep(turn.steps, 'check', {
          status: 'done',
          detail: event.data.passed ? undefined : event.data.findings.map((f) => f.text).join(' '),
        }),
      };
    case 'run.paused':
      return { ...turn, status: 'paused', pause: event.data, credits: event.data.credits };
    case 'run.resumed':
      return { ...turn, status: turn.steps.some((s) => s.status === 'active') ? 'executing' : 'planning', pause: undefined };
    case 'run.stop_requested':
      return { ...turn, status: 'stopping', stopping: true };
    case 'run.result':
      return {
        ...turn,
        status: event.data.status,
        endedAt: at,
        result: event.data,
        credits: event.data.credits,
        checking: false,
        answerText: event.data.answer ?? turn.answerText,
        citations: mergeCitations(turn.citations, event.data.citations),
        steps: skipQueued(turn.steps, turn.stopping ? STOPPED : undefined),
        question: undefined,
        pause: undefined,
      };
    case 'run.failed':
      return {
        ...turn,
        status: 'failed',
        endedAt: at,
        failure: { error: event.data.error, version: event.data.version, suggestion: event.data.suggestion },
        credits: event.data.credits,
        checking: false,
        steps: skipQueued(turn.steps),
        pause: undefined,
      };
    case 'run.cancelled':
      return {
        ...turn,
        status: 'cancelled',
        endedAt: at,
        cancelled: { by: event.data.by, while: event.data.while, changed: turn.revisions.length > 0 },
        checking: false,
        steps: skipQueued(turn.steps, STOPPED),
        pause: undefined,
      };
    default:
      return turn;
  }
}

/** Run-wide effects of one event: locks and markers. */
function applyToRun(state: RunState, turn: Turn, event: RunEvent): RunState {
  const runId = event.run_id;
  switch (event.type) {
    case 'run.acknowledged':
      // Markers clear when the next run starts (02-editor §5.1).
      return { ...state, markers: {} };
    case 'run.lock.acquired':
      return { ...state, locks: { ...state.locks, ...Object.fromEntries(event.data.item_ids.map((id) => [id, runId])) } };
    case 'run.lock.released':
      return { ...state, locks: Object.fromEntries(Object.entries(state.locks).filter(([id]) => !event.data.item_ids.includes(id))) };
    case 'run.operation.applied': {
      const marker: Marker = { turnId: turn.id, runId, revision: event.data.revision };
      return { ...state, markers: { ...state.markers, ...Object.fromEntries(event.data.item_ids.map((id) => [id, marker])) } };
    }
    case 'run.result':
    case 'run.failed':
    case 'run.cancelled':
      return { ...state, locks: releaseRun(state.locks, runId) };
    default:
      return state;
  }
}

function ensureTurn(state: RunState, event: RunEvent): [RunState, Turn | undefined] {
  const existing = state.turns.find((turn) => turn.runId === event.run_id);
  if (existing) return [state, existing];
  // Another tab, a reload mid-run, or the stream outran POST /runs: start the turn from the event.
  if (event.type !== 'run.queued' && event.type !== 'run.acknowledged') return [state, undefined];
  const mode = event.type === 'run.acknowledged' ? event.data.mode : 'edit';
  const turn = blankTurn(event.run_id, event.run_id, '', [], mode, 'sending');
  return [{ ...state, turns: [...state.turns, turn] }, turn];
}

function applyEvent(state: RunState, event: RunEvent): RunState {
  const [withTurn, turn] = ensureTurn(state, event);
  if (!turn) return state;
  const next = patchTurn(withTurn, turn.id, (t) => applyToTurn(t, event));
  return applyToRun(next, turn, event);
}

/** events.md §7.3: drop duplicates, buffer past a gap, apply ephemeral events only at the current seq. */
function receive(state: RunState, event: RunEvent): RunState {
  const runId = event.run_id;
  const last = state.lastSeq[runId] ?? 0;
  if (!event.durable || EPHEMERAL_RUN_EVENTS.has(event.type)) {
    return event.seq === last ? applyEvent(state, event) : state;
  }
  if (event.seq <= last) return state;
  if (event.seq > last + 1) {
    const queued = state.buffered[runId] ?? [];
    if (queued.some((e) => e.seq === event.seq)) return state;
    return {
      ...state,
      buffered: { ...state.buffered, [runId]: [...queued, event].sort((a, b) => a.seq - b.seq) },
      backfill: { ...state.backfill, [runId]: last },
    };
  }
  let next = applyEvent(state, event);
  let seq = event.seq;
  let rest = (next.buffered[runId] ?? []).filter((e) => e.seq > seq);
  while (rest[0]?.seq === seq + 1) {
    next = applyEvent(next, rest[0]);
    seq += 1;
    rest = rest.slice(1);
  }
  const { [runId]: _gone, ...backfill } = next.backfill;
  return {
    ...next,
    lastSeq: { ...next.lastSeq, [runId]: seq },
    buffered: rest.length ? { ...next.buffered, [runId]: rest } : omit(next.buffered, runId),
    backfill: rest.length ? { ...backfill, [runId]: seq } : backfill,
  };
}

function omit<T>(record: Record<string, T>, key: string): Record<string, T> {
  const { [key]: _gone, ...rest } = record;
  return rest;
}

/** Merge the turn the stream created with the local turn that sent it. */
function bind(state: RunState, turnId: string, run: Run): RunState {
  const local = state.turns.find((turn) => turn.id === turnId);
  if (!local) return state;
  const streamed = state.turns.find((turn) => turn.runId === run.id && turn.id !== turnId);
  const base = streamed ?? turnFromRun(run, local.id);
  const merged: Turn = { ...base, id: local.id, runId: run.id, prompt: local.prompt, chips: local.chips, mode: local.mode, retryOf: local.retryOf, startedAt: local.startedAt ?? base.startedAt };
  const turns = state.turns.filter((turn) => turn !== streamed).map((turn) => (turn.id === turnId ? merged : turn));
  const markers = Object.fromEntries(Object.entries(state.markers).map(([item, m]) => [item, m.runId === run.id ? { ...m, turnId } : m]));
  // With no events yet, the snapshot is the state up to its seq; once the stream started, its seq stands.
  const lastSeq = streamed ? state.lastSeq : { ...state.lastSeq, [run.id]: Math.max(state.lastSeq[run.id] ?? 0, run.last_event_seq) };
  return { ...state, turns, markers, lastSeq };
}

export function reduceRun(state: RunState, action: RunAction): RunState {
  switch (action.kind) {
    case 'send':
      return {
        ...state,
        turns: [...state.turns, { ...blankTurn(action.turnId, null, action.prompt, action.chips, action.mode, 'sending'), startedAt: action.at, retryOf: action.retryOf }],
      };
    case 'send.failed':
      return patchTurn(state, action.turnId, (turn) => ({ ...turn, status: 'send_failed', sendError: action.error }));
    case 'bind':
      return bind(state, action.turnId, action.run);
    case 'hydrate': {
      const known = new Set(state.turns.map((turn) => turn.runId));
      const older = action.runs.filter((run) => !known.has(run.id)).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)).map((run) => turnFromRun(run));
      const lastSeq = { ...state.lastSeq };
      for (const run of action.runs) lastSeq[run.id] = Math.max(lastSeq[run.id] ?? 0, run.last_event_seq);
      const order = (turn: Turn) => turn.startedAt ?? Number.POSITIVE_INFINITY;
      const turns = [...older, ...state.turns].sort((a, b) => (order(a) === order(b) ? 0 : order(a) < order(b) ? -1 : 1));
      return { ...state, turns, lastSeq };
    }
    case 'event':
      return receive(state, action.event);
    case 'answer':
      return patchByRun(state, action.runId, (turn) =>
        turn.question ? { ...turn, question: { ...turn.question, chosenId: action.choiceId === 'skip' ? undefined : action.choiceId, skipped: action.choiceId === 'skip', by: 'user' } } : turn,
      );
    case 'decide':
      return patchByRun(state, action.runId, (turn) => (turn.pause ? { ...turn, pause: { ...turn.pause, decided: action.decision } } : turn));
    case 'stop':
      return patchByRun(state, action.runId, (turn) => (isTerminal(turn.status) ? turn : { ...turn, stopping: true, status: 'stopping' }));
    case 'undone':
      return patchTurn(state, action.turnId, (turn) => ({ ...turn, undone: action.undone }));
    case 'markers.clear':
      return { ...state, markers: action.itemIds ? omitMany(state.markers, action.itemIds) : {} };
    case 'remove':
      return { ...state, turns: state.turns.filter((turn) => turn.id !== action.turnId) };
    case 'reset':
      return INITIAL_RUN_STATE;
    default:
      return state;
  }
}

function patchByRun(state: RunState, runId: string, patch: (turn: Turn) => Turn): RunState {
  return { ...state, turns: state.turns.map((turn) => (turn.runId === runId ? patch(turn) : turn)) };
}

function omitMany<T>(record: Record<string, T>, keys: string[]): Record<string, T> {
  return Object.fromEntries(Object.entries(record).filter(([key]) => !keys.includes(key)));
}

/* ───────────── selectors ───────────── */

/** Caches on the input reference, so list selectors return a stable array between unrelated updates. */
function memo<I, O>(pick: (s: RunState) => I, build: (input: I) => O): (s: RunState) => O {
  let lastIn: I | typeof UNSET = UNSET;
  let lastOut: O;
  return (s) => {
    const input = pick(s);
    if (input !== lastIn) {
      lastIn = input;
      lastOut = build(input);
    }
    return lastOut;
  };
}
const UNSET = Symbol('unset');

export const selectTurns = (s: RunState): Turn[] => s.turns;
export const selectTurn = (turnId: string) => (s: RunState): Turn | undefined => s.turns.find((turn) => turn.id === turnId);
/** The run doing work now (not queued, not finished, not a failed send). */
export const selectActiveTurn = (s: RunState): Turn | undefined =>
  s.turns.find((turn) => !isTerminal(turn.status) && turn.status !== 'queued' && turn.status !== 'send_failed');
export const selectIsRunning = (s: RunState): boolean => selectActiveTurn(s) !== undefined;
/** "Up next": queued prompts in queue order. */
export const selectQueue = memo(
  (s) => s.turns,
  (turns) => turns.filter((turn) => turn.status === 'queued').sort((a, b) => (a.queuePosition ?? 0) - (b.queuePosition ?? 0)),
);
export const selectIsLocked = (itemId: string) => (s: RunState): boolean => itemId in s.locks;
export const selectLockedIds = memo((s) => s.locks, (locks) => Object.keys(locks));
export const selectMarker = (itemId: string) => (s: RunState): Marker | undefined => s.markers[itemId];
export const selectMarkers = (s: RunState): Record<string, Marker> => s.markers;
export const selectBackfill = (s: RunState): Record<string, number> => s.backfill;

/* ───────────── store ───────────── */

export interface RunStore {
  store: StoreApi<RunState>;
  dispatch(action: RunAction): void;
  /** For the doc store's `isLocked` dependency. */
  isLocked(itemId: string): boolean;
}

export function createRunStore(initial: RunState = INITIAL_RUN_STATE): RunStore {
  const store = createStore<RunState>(() => initial);
  return {
    store,
    dispatch: (action) => store.setState((state) => reduceRun(state, action), true),
    isLocked: (itemId) => itemId in store.getState().locks,
  };
}

/** React binding: `useRun(runs, selectActiveTurn)`. */
export function useRun<T>(runs: RunStore, selector: (state: RunState) => T): T {
  return useStore(runs.store, selector);
}
