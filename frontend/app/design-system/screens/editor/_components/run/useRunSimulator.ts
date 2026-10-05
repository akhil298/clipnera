'use client';

import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import type { PromptContext } from '@/components/ui/ContextChip';
import type { PromptMode } from '@/components/ui/PromptBar';
import type { RunStep } from '@/components/ui/StepList';

import type { Credits, ErrorObject, RunEvent, RunStatus, Suggestion } from './events';
import { type Beat, followUpBeats, type Scenario, scenarioById } from './scenarios';

/* ───────────────────────── view state ───────────────────────── */

export interface TurnView {
  id: string;
  prompt: string;
  chips: PromptContext[];
  mode: PromptMode;
  /** `sending` is the client-only moment before `run.acknowledged` (01 §5 step 1). */
  status: RunStatus | 'sending';
  startedAt: number;
  endedAt?: number;
  planText: string;
  planSteps?: { id: string; label: string }[];
  credits?: Credits;
  steps: RunStep[];
  checking: boolean;
  question?: { id: string; text: string; choices: { id: string; label: string; hint?: string }[]; chosenId?: string };
  pause?: Extract<RunEvent, { type: 'run.paused' }>['data'] & { decided?: string };
  stopping: boolean;
  answerText: string;
  findings: { severity: 'info' | 'warn'; text: string }[];
  result?: Extract<RunEvent, { type: 'run.result' }>['data'];
  failure?: { error: ErrorObject; version: { id: string; name: string } | null; suggestion?: Suggestion };
  cancelled?: { while: 'queued' | 'running'; changed: boolean };
  undone: boolean;
  pick?: Scenario['pick'];
  retryOf?: string;
}

export interface EditorView {
  revision: number;
  baseRevision: number;
  locked: string[];
  /** Items to outline for 600 ms; `key` restarts the animation on each operation. */
  highlight: { ids: string[]; key: number } | null;
  changedRange: [number, number] | null;
  quality: 'preview' | 'full';
  versionCount: number;
  versionPulse: number;
  balance: number;
  online: boolean;
  catchingUp: boolean;
}

export interface QueuedPrompt {
  id: string;
  prompt: string;
  chips: PromptContext[];
}

interface State {
  turns: TurnView[];
  editor: EditorView;
}

const INITIAL_EDITOR: EditorView = {
  revision: 40,
  baseRevision: 40,
  locked: [],
  highlight: null,
  changedRange: null,
  quality: 'full',
  versionCount: 11,
  versionPulse: 0,
  balance: 1240,
  online: true,
  catchingUp: false,
};

type Action =
  | { kind: 'reset'; revision: number }
  | { kind: 'send'; turn: TurnView }
  | { kind: 'event'; turnId: string; event: RunEvent }
  | { kind: 'decide'; turnId: string; decision: string }
  | { kind: 'undo'; turnId: string; undone: boolean; revision: number }
  | { kind: 'catch-up-done' };

const STOP_LABEL = 'stopped before this step';

function patchTurn(state: State, turnId: string, patch: (turn: TurnView) => TurnView): State {
  return { ...state, turns: state.turns.map((turn) => (turn.id === turnId ? patch(turn) : turn)) };
}

function setStep(steps: RunStep[], id: string, patch: Partial<RunStep>): RunStep[] {
  return steps.map((step) => (step.id === id ? { ...step, ...patch } : step));
}

/** Maps one event onto the turn and the editor. One case per event type in events.md §3. */
function applyEvent(state: State, turnId: string, event: RunEvent): State {
  const editor = state.editor;
  const now = Date.now();
  switch (event.type) {
    case 'run.queued':
      return patchTurn(state, turnId, (turn) => ({ ...turn, status: 'queued' }));
    case 'run.acknowledged':
      return patchTurn(state, turnId, (turn) => ({ ...turn, status: 'acknowledged', credits: event.data.credits }));
    case 'run.plan.delta':
      return patchTurn(state, turnId, (turn) => ({ ...turn, status: 'planning', planText: turn.planText + event.data.text }));
    case 'run.plan':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        status: 'planning',
        planText: event.data.sentences.join(' '),
        planSteps: event.data.steps,
        credits: event.data.credits,
        steps: turn.mode === 'plan' ? [] : event.data.steps.map((step) => ({ id: step.id, label: step.label, status: 'queued' as const })),
      }));
    case 'run.message.delta':
      return patchTurn(state, turnId, (turn) => ({ ...turn, status: 'planning', answerText: turn.answerText + event.data.text }));
    case 'run.question':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        status: 'awaiting_input',
        question: { id: event.data.question_id, text: event.data.text, choices: event.data.choices },
      }));
    case 'run.answered':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        status: turn.steps.some((step) => step.status === 'active') ? 'executing' : 'planning',
        question: turn.question && { ...turn.question, chosenId: event.data.skipped ? 'skip' : event.data.choice_id },
      }));
    case 'run.step.started':
      return patchTurn(state, turnId, (turn) => {
        const known = turn.steps.some((step) => step.id === event.data.step_id);
        const steps = known
          ? setStep(turn.steps, event.data.step_id, { label: event.data.label, status: 'active', detail: undefined, progress: undefined })
          : [...turn.steps, { id: event.data.step_id, label: event.data.label, status: 'active' as const }];
        return { ...turn, status: turn.stopping ? 'stopping' : 'executing', steps };
      });
    case 'run.step.progress': {
      const { done, total, percent, label } = event.data;
      const text = label ?? (done !== undefined && total !== undefined ? `${done} of ${total}` : percent !== undefined ? `${percent}%` : undefined);
      return patchTurn(state, turnId, (turn) => ({ ...turn, steps: setStep(turn.steps, event.data.step_id, { progress: text }) }));
    }
    case 'run.step.completed':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        steps: setStep(turn.steps, event.data.step_id, { status: 'done', detail: event.data.summary, progress: undefined }),
      }));
    case 'run.step.failed':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        steps: setStep(
          turn.steps,
          event.data.step_id,
          event.data.will_retry
            ? { status: 'active', progress: 'Trying again', detail: event.data.error.message }
            : { status: 'failed', detail: event.data.error.message, progress: undefined },
        ),
      }));
    case 'run.lock.acquired':
      return { ...state, editor: { ...editor, locked: Array.from(new Set([...editor.locked, ...event.data.item_ids])) } };
    case 'run.lock.released':
      return { ...state, editor: { ...editor, locked: editor.locked.filter((id) => !event.data.item_ids.includes(id)) } };
    case 'run.operation.applied':
      // Idempotent by revision (events.md §3.3 invariant 2).
      if (event.data.revision <= editor.revision) return state;
      return {
        ...state,
        editor: {
          ...editor,
          revision: event.data.revision,
          highlight: { ids: event.data.item_ids, key: event.data.revision },
          changedRange: event.data.changed_ranges[0] ?? null,
          quality: 'preview',
        },
      };
    case 'run.check.started':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        status: 'checking',
        checking: true,
        steps: [...turn.steps, { id: 'check', label: 'Checking the result', status: 'active' }],
      }));
    case 'run.check.completed':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        findings: event.data.findings,
        steps: setStep(turn.steps, 'check', {
          status: 'done',
          detail: event.data.passed ? 'Watched the result and listened to the audio' : event.data.findings.map((finding) => finding.text).join(' '),
        }),
      }));
    case 'run.paused':
      return patchTurn(state, turnId, (turn) => ({ ...turn, status: 'paused', pause: event.data }));
    case 'run.resumed':
      return patchTurn(state, turnId, (turn) => ({ ...turn, status: 'executing' }));
    case 'run.stop_requested':
      return patchTurn(state, turnId, (turn) => ({ ...turn, status: 'stopping', stopping: true }));
    case 'run.result':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        status: event.data.status,
        endedAt: now,
        result: event.data,
        steps: turn.steps.map((step) => (step.status === 'queued' ? { ...step, status: 'skipped' as const, detail: STOP_LABEL } : step)),
      }));
    case 'run.failed':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        status: 'failed',
        endedAt: now,
        failure: event.data,
        steps: turn.steps.map((step) => (step.status === 'queued' ? { ...step, status: 'skipped' as const } : step)),
      }));
    case 'run.cancelled':
      return patchTurn(state, turnId, (turn) => ({
        ...turn,
        status: 'cancelled',
        endedAt: now,
        cancelled: { while: event.data.while, changed: false },
        steps: turn.steps.map((step) => (step.status === 'queued' ? { ...step, status: 'skipped' as const } : step)),
      }));
    case 'version.created':
      return { ...state, editor: { ...editor, versionCount: editor.versionCount + 1, versionPulse: editor.versionPulse + 1, locked: [] } };
    case 'credits.updated':
      return { ...state, editor: { ...editor, balance: event.data.balance } };
    case 'sync.reset':
      return { ...state, editor: { ...editor, catchingUp: true } };
    case 'job.succeeded':
      return { ...state, editor: { ...editor, quality: 'full' } };
    case 'client.connection':
      return { ...state, editor: { ...editor, online: event.data.online } };
    default:
      return state;
  }
}

function reducer(state: State, action: Action): State {
  switch (action.kind) {
    case 'reset':
      return { turns: [], editor: { ...INITIAL_EDITOR, revision: action.revision, baseRevision: action.revision } };
    case 'send':
      return { ...state, turns: [...state.turns, action.turn] };
    case 'event':
      return applyEvent(state, action.turnId, action.event);
    case 'decide':
      return patchTurn(state, action.turnId, (turn) => ({ ...turn, pause: turn.pause && { ...turn.pause, decided: action.decision } }));
    case 'undo':
      return {
        ...patchTurn(state, action.turnId, (turn) => ({ ...turn, undone: action.undone })),
        editor: {
          ...state.editor,
          revision: action.revision,
          highlight: null,
          versionCount: state.editor.versionCount + 1,
          versionPulse: state.editor.versionPulse + 1,
        },
      };
    case 'catch-up-done':
      return { ...state, editor: { ...state.editor, catchingUp: false } };
    default:
      return state;
  }
}

/* ───────────────────────── engine ───────────────────────── */

export type Speed = 0.5 | 1 | 2;

interface Cursor {
  turnId: string;
  scenario: Scenario;
  beats: Beat[];
  index: number;
  gate: 'answer' | 'decision' | null;
  /** Events that arrive while the connection is down; replayed on `sync.reset`. */
  buffered: RunEvent[];
  online: boolean;
}

let turnSeq = 0;
const newTurnId = () => `turn-${++turnSeq}`;

function makeTurn(prompt: string, chips: PromptContext[], mode: PromptMode, extra: Partial<TurnView> = {}): TurnView {
  return {
    id: newTurnId(),
    prompt,
    chips,
    mode,
    status: 'sending',
    startedAt: Date.now(),
    planText: '',
    steps: [],
    checking: false,
    stopping: false,
    answerText: '',
    findings: [],
    undone: false,
    ...extra,
  };
}

/**
 * Replays scripted run events through the same view model a real run store
 * would build from the event stream. Timers only; no network.
 */
export function useRunSimulator(initialRevision = 40) {
  const [state, dispatch] = useReducer(reducer, { turns: [], editor: { ...INITIAL_EDITOR, revision: initialRevision, baseRevision: initialRevision } });
  const [speed, setSpeed] = useState<Speed>(1);
  const [queue, setQueue] = useState<QueuedPrompt[]>([]);
  const [log, setLog] = useState<{ seq: number; type: string; at: number; buffered: boolean }[]>([]);
  const cursor = useRef<Cursor | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speedRef = useRef(speed);
  speedRef.current = speed;
  const queueRef = useRef(queue);
  queueRef.current = queue;
  const stateRef = useRef(state);
  stateRef.current = state;

  const clear = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  const emit = useCallback((turnId: string, event: RunEvent) => {
    const current = cursor.current;
    if (current && event.type === 'client.connection') current.online = event.data.online;
    const buffered = Boolean(current && !current.online && event.type !== 'client.connection');
    setLog((items) => [...items, { seq: items.length + 1, type: event.type, at: Date.now(), buffered }]);
    if (current && buffered) {
      current.buffered.push(event);
      return;
    }
    dispatch({ kind: 'event', turnId, event });
    if (event.type === 'sync.reset' && current) {
      // The snapshot refetch: everything missed lands at once, then live events resume.
      current.buffered.forEach((missed) => dispatch({ kind: 'event', turnId, event: missed }));
      current.buffered = [];
      setTimeout(() => dispatch({ kind: 'catch-up-done' }), 600);
    }
  }, []);

  const startNext = useRef<() => void>(() => undefined);

  const step = useCallback(() => {
    const current = cursor.current;
    if (!current) return;
    const beat = current.beats[current.index];
    if (!beat) {
      cursor.current = null;
      startNext.current();
      return;
    }
    if ('gate' in beat) {
      current.gate = beat.gate;
      return;
    }
    timer.current = setTimeout(() => {
      current.index += 1;
      emit(current.turnId, beat.event);
      step();
    }, beat.after / speedRef.current);
  }, [emit]);

  const run = useCallback(
    (turn: TurnView, scenario: Scenario, beats: Beat[]) => {
      clear();
      dispatch({ kind: 'send', turn });
      cursor.current = { turnId: turn.id, scenario, beats, index: 0, gate: null, buffered: [], online: true };
      step();
    },
    [step],
  );

  startNext.current = () => {
    const [next, ...rest] = queueRef.current;
    if (!next) return;
    setQueue(rest);
    const base = stateRef.current.editor.revision;
    const scenario: Scenario = { ...scenarioById('happy'), id: 'follow-up', prompt: next.prompt, beats: followUpBeats(base) };
    run(makeTurn(next.prompt, next.chips, 'edit'), scenario, scenario.beats);
  };

  /** Starts a scenario as if the person had pressed Enter. Clears the conversation unless `keep`. */
  const start = useCallback(
    (scenarioId: string, options: { keep?: boolean; prompt?: string; retryOf?: string } = {}) => {
      clear();
      const scenario = scenarioById(scenarioId);
      if (!options.keep) {
        dispatch({ kind: 'reset', revision: scenario.baseRevision });
        setQueue([]);
        setLog([]);
      }
      run(makeTurn(options.prompt ?? scenario.prompt, scenario.chips, scenario.mode, { pick: scenario.pick, retryOf: options.retryOf }), scenario, scenario.beats);
    },
    [run],
  );

  const resumeGate = () => {
    const current = cursor.current;
    if (!current || !current.gate) return;
    current.gate = null;
    current.index += 1;
    step();
  };

  const answer = (choiceId: string | 'skip') => {
    const current = cursor.current;
    if (!current || current.gate !== 'answer') return;
    const question = stateRef.current.turns.find((turn) => turn.id === current.turnId)?.question;
    emit(current.turnId, {
      type: 'run.answered',
      data: { question_id: question?.id ?? 'q', choice_id: choiceId === 'skip' ? undefined : choiceId, skipped: choiceId === 'skip', by: 'user' },
    });
    resumeGate();
  };

  const decide = (decision: 'continue' | 'finish' | 'add_credits') => {
    const current = cursor.current;
    if (!current || current.gate !== 'decision') return;
    dispatch({ kind: 'decide', turnId: current.turnId, decision });
    if (decision === 'finish' && current.scenario.finish) {
      current.beats = current.beats.slice(0, current.index + 1).concat(current.scenario.finish);
    }
    resumeGate();
  };

  /** Stop: halts at the next safe point. Completed work stays as a version (01 §5). */
  const stop = () => {
    const current = cursor.current;
    if (!current) return;
    clear();
    const turn = stateRef.current.turns.find((candidate) => candidate.id === current.turnId);
    const changed = stateRef.current.editor.revision > stateRef.current.editor.baseRevision;
    const active = turn?.steps.find((candidate) => candidate.status === 'active');
    const done = (turn?.steps ?? []).filter((candidate) => candidate.status === 'done' && candidate.id !== 'check');
    const remaining = (turn?.steps ?? []).filter((candidate) => candidate.status === 'queued' || candidate.status === 'active');
    const tail: Beat[] = [{ after: 0, event: { type: 'run.stop_requested', data: { by: 'you' } } }];
    tail.push({ after: 700, event: { type: 'run.lock.released', data: { step_id: active?.id ?? 'stop', item_ids: stateRef.current.editor.locked } } });
    if (!changed) {
      tail.push({ after: 500, event: { type: 'run.cancelled', data: { by: 'user', while: 'running' } } });
    } else {
      const name = done.map((candidate) => candidate.detail ?? candidate.label).join(', ') || 'Partial edit';
      tail.push({
        after: 500,
        event: {
          type: 'run.result',
          data: {
            status: 'partial',
            version: { id: 'v_stop', name: done[done.length - 1]?.label.replace(/^(\w+)ing\b/, '$1ed') ?? name, result_revision: stateRef.current.editor.revision },
            summary: {
              done: done.map((candidate) => candidate.detail ?? candidate.label),
              not_done: remaining.map((candidate) => ({ text: candidate.label, reason: STOP_LABEL })),
            },
            suggestions: remaining.length ? [{ label: 'Try the rest', prompt: remaining.map((candidate) => candidate.label).join(' and ').toLowerCase() }] : [],
            credits: turn?.credits ?? { estimate: 0, held: 0, spent: 0 },
            duration_ms: 0,
          },
        },
      });
      tail.push({ after: 60, event: { type: 'version.created', data: { version_id: 'v_stop', name } } });
    }
    current.beats = tail;
    current.index = 0;
    current.gate = null;
    step();
  };

  /** Sending while a run is active adds to the visible queue (backend §4.4). */
  const enqueue = (prompt: string, chips: PromptContext[] = []) => {
    setQueue((items) => [...items, { id: `q-${Date.now()}`, prompt, chips }]);
  };

  /** Undo restores the run's base revision; Redo returns to its result (both make a new version, backend §4.5). */
  const undo = (turnId: string, undone: boolean) => {
    const turn = stateRef.current.turns.find((candidate) => candidate.id === turnId);
    const target = undone ? stateRef.current.editor.baseRevision : (turn?.result?.version?.result_revision ?? stateRef.current.editor.revision);
    dispatch({ kind: 'undo', turnId, undone, revision: target });
  };

  const reset = (revision = initialRevision) => {
    clear();
    cursor.current = null;
    setQueue([]);
    setLog([]);
    dispatch({ kind: 'reset', revision });
  };

  useEffect(() => () => clear(), []);

  const active = state.turns.find((turn) => !['succeeded', 'partial', 'failed', 'cancelled'].includes(turn.status));

  return {
    turns: state.turns,
    editor: state.editor,
    log,
    running: Boolean(active),
    activeTurn: active,
    queue,
    setQueue,
    speed,
    setSpeed,
    start,
    answer,
    decide,
    stop,
    enqueue,
    undo,
    reset,
  };
}

export type RunSimulator = ReturnType<typeof useRunSimulator>;
