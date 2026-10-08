/**
 * Development run simulator: replays the scripted runs in ./scenarios.ts into a run store, with
 * real envelopes (run_id, seq, durable), so the conversation, timeline markers and locks can be
 * built before the run routes (EB-3) and the event stream (EB-1) exist. Ported from the mockup's
 * useRunSimulator, but framework-free: timers only, no React, no network.
 *
 *   const sim = createRunSimulator({ runs, onSideEvent, onOperation: (e) => doc.applyRemote(e.data) });
 *   sim.start('happy');
 */
import { EPHEMERAL_RUN_EVENTS, type Run, type RunEvent, type RunEventOf, type WireChip } from '@/lib/api/editor/types';

import type { RunStore, Turn } from '../run-store';
import { contextFromWire } from '../selection';
import { followUpBeats, scenarioById, type Beat, type DevEvent, type DevRunEvent, type DevSideEvent, type Scenario } from './scenarios';

export type SimulatorSpeed = 0.5 | 1 | 2;

export interface Timers {
  set(fn: () => void, ms: number): unknown;
  clear(handle: unknown): void;
}

export interface SimulatorOptions {
  runs: RunStore;
  /** version.created, credits.updated, sync.reset, job.succeeded and the connection state. */
  onSideEvent?: (event: DevSideEvent) => void;
  /** Each `run.operation.applied`, e.g. to feed a doc store (the scripted ops are empty). */
  onOperation?: (event: RunEventOf<'run.operation.applied'>) => void;
  timers?: Timers;
  now?: () => number;
}

export interface RunSimulator {
  /** Sends a scenario's prompt as if Enter was pressed; clears the conversation unless `keep`. Returns the turn id. */
  start(scenarioId: string, options?: { keep?: boolean; prompt?: string }): string;
  /** Picks a choice on the open question (or skips it). */
  answer(choiceId: string | 'skip'): void;
  /** Decides on a pause: continue, finish with what's done, or add credits. */
  decide(decision: 'continue' | 'finish' | 'add_credits'): void;
  /** Stops at the next safe point; completed work stays as a version. */
  stop(): void;
  /** A prompt sent while a run is active joins the queue and runs after it. */
  enqueue(prompt: string, chips?: WireChip[]): string;
  setSpeed(speed: SimulatorSpeed): void;
  reset(): void;
  dispose(): void;
}

interface Cursor {
  turnId: string;
  runId: string;
  scenario: Scenario;
  beats: Beat[];
  index: number;
  gate: 'answer' | 'decision' | null;
}

const STOP_LABEL = 'stopped before this step';

const defaultTimers: Timers = {
  set: (fn, ms) => setTimeout(fn, ms),
  clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

const isSide = (event: DevEvent): event is DevSideEvent =>
  !event.type.startsWith('run.');

export function createRunSimulator({ runs, onSideEvent, onOperation, timers = defaultTimers, now = Date.now }: SimulatorOptions): RunSimulator {
  let speed: SimulatorSpeed = 1;
  let cursor: Cursor | null = null;
  let timer: unknown = null;
  let online = true;
  let buffered: RunEvent[] = [];
  let counter = 0;
  const seqs = new Map<string, number>();
  const queue: { turnId: string; runId: string; prompt: string }[] = [];

  const clear = () => {
    if (timer !== null) timers.clear(timer);
    timer = null;
  };

  const envelope = (runId: string, event: DevRunEvent): RunEvent => {
    const durable = !EPHEMERAL_RUN_EVENTS.has(event.type);
    const seq = (seqs.get(runId) ?? 0) + (durable ? 1 : 0);
    seqs.set(runId, seq);
    return { ...event, run_id: runId, seq, durable, ts: new Date(now()).toISOString() } as RunEvent;
  };

  const deliver = (event: RunEvent) => {
    runs.dispatch({ kind: 'event', event });
    if (event.type === 'run.operation.applied') onOperation?.(event);
  };

  const emit = (runId: string, event: DevEvent) => {
    if (isSide(event)) {
      if (event.type === 'client.connection') online = event.data.online;
      onSideEvent?.(event);
      if (event.type === 'sync.reset') {
        // The snapshot refetch: everything missed lands at once, then live events resume.
        buffered.forEach(deliver);
        buffered = [];
      }
      return;
    }
    const wrapped = envelope(runId, event);
    if (online) deliver(wrapped);
    else buffered.push(wrapped);
  };

  const step = () => {
    const current = cursor;
    if (!current) return;
    const beat = current.beats[current.index];
    if (!beat) {
      cursor = null;
      startNext();
      return;
    }
    if ('gate' in beat) {
      current.gate = beat.gate;
      return;
    }
    timer = timers.set(() => {
      current.index += 1;
      emit(current.runId, beat.event);
      step();
    }, beat.after / speed);
  };

  const snapshot = (runId: string, prompt: string, scenario: Pick<Scenario, 'mode' | 'chips'>, status: Run['status']): Run => ({
    id: runId,
    project_id: 'dev',
    status,
    mode: scenario.mode,
    prompt,
    chips: scenario.chips,
    credits: { estimate: 0, held: 0, spent: 0 },
    last_event_seq: 0,
    created_at: new Date(now()).toISOString(),
  });

  const send = (prompt: string, scenario: Pick<Scenario, 'mode' | 'chips'>, status: Run['status']) => {
    counter += 1;
    const turnId = `dev-turn-${counter}`;
    const runId = `dev-run-${counter}`;
    runs.dispatch({ kind: 'send', turnId, prompt, chips: scenario.chips.map(contextFromWire), mode: scenario.mode, at: now() });
    runs.dispatch({ kind: 'bind', turnId, run: snapshot(runId, prompt, scenario, status) });
    return { turnId, runId };
  };

  const run = (ids: { turnId: string; runId: string }, scenario: Scenario, beats: Beat[]) => {
    clear();
    cursor = { ...ids, scenario, beats, index: 0, gate: null };
    step();
  };

  const startNext = () => {
    const next = queue.shift();
    if (!next) return;
    queue.forEach((item, index) => emit(item.runId, { type: 'run.queue.updated', data: { queue_position: index + 1 } }));
    const base = Math.max(0, ...runs.store.getState().turns.flatMap((turn) => turn.revisions), scenarioById('happy').baseRevision);
    const scenario: Scenario = { ...scenarioById('happy'), id: 'follow-up', prompt: next.prompt, beats: followUpBeats(base) };
    run(next, scenario, scenario.beats);
  };

  const resumeGate = () => {
    if (!cursor?.gate) return;
    cursor.gate = null;
    cursor.index += 1;
    step();
  };

  const activeTurn = (): Turn | undefined => runs.store.getState().turns.find((turn) => turn.id === cursor?.turnId);

  return {
    start(scenarioId, options = {}) {
      clear();
      const scenario = scenarioById(scenarioId);
      if (!options.keep) {
        cursor = null;
        queue.length = 0;
        buffered = [];
        online = true;
        runs.dispatch({ kind: 'reset' });
      }
      const ids = send(options.prompt ?? scenario.prompt, scenario, 'acknowledged');
      run(ids, scenario, scenario.beats);
      return ids.turnId;
    },

    answer(choiceId) {
      const current = cursor;
      if (!current || current.gate !== 'answer') return;
      const question = activeTurn()?.question;
      runs.dispatch({ kind: 'answer', runId: current.runId, choiceId });
      emit(current.runId, {
        type: 'run.answered',
        data: { question_id: question?.question_id ?? 'q', choice_id: choiceId === 'skip' ? undefined : choiceId, skipped: choiceId === 'skip', by: 'user' },
      });
      resumeGate();
    },

    decide(decision) {
      const current = cursor;
      if (!current || current.gate !== 'decision') return;
      runs.dispatch({ kind: 'decide', runId: current.runId, decision });
      if (decision === 'finish' && current.scenario.finish) {
        current.beats = current.beats.slice(0, current.index + 1).concat(current.scenario.finish);
      }
      resumeGate();
    },

    stop() {
      const current = cursor;
      if (!current) return;
      clear();
      runs.dispatch({ kind: 'stop', runId: current.runId });
      const turn = activeTurn();
      const steps = turn?.steps ?? [];
      const done = steps.filter((s) => s.status === 'done' && s.id !== 'check');
      const remaining = steps.filter((s) => s.status === 'queued' || s.status === 'active');
      const locked = Object.entries(runs.store.getState().locks).flatMap(([item, holder]) => (holder === current.runId ? [item] : []));
      const revision = turn?.revisions.at(-1);
      const tail: Beat[] = [
        { after: 0, event: { type: 'run.stop_requested', data: { by: 'you' } } },
        { after: 700, event: { type: 'run.lock.released', data: { step_id: remaining[0]?.id ?? 'stop', item_ids: locked } } },
      ];
      if (revision === undefined) {
        tail.push({ after: 500, event: { type: 'run.cancelled', data: { by: 'user', while: 'running' } } });
      } else {
        const name = done.at(-1)?.label ?? 'Partial edit';
        tail.push(
          {
            after: 500,
            event: {
              type: 'run.result',
              data: {
                status: 'partial',
                version: { id: `v_${revision}`, name, result_revision: revision },
                summary: {
                  done: done.map((s) => s.detail ?? s.label),
                  not_done: remaining.map((s) => ({ text: s.label, reason: STOP_LABEL })),
                },
                suggestions: remaining.length ? [{ label: 'Try the rest', prompt: remaining.map((s) => s.label).join(' and ').toLowerCase() }] : [],
                credits: turn?.credits ?? { estimate: 0, held: 0, spent: 0 },
                duration_ms: 0,
              },
            },
          },
          { after: 60, event: { type: 'version.created', data: { version_id: `v_${revision}`, name } } },
        );
      }
      current.beats = tail;
      current.index = 0;
      current.gate = null;
      step();
    },

    enqueue(prompt, chips = []) {
      const ids = send(prompt, { mode: 'edit', chips }, 'queued');
      queue.push({ ...ids, prompt });
      emit(ids.runId, { type: 'run.queued', data: { queue_position: queue.length, prompt_preview: prompt.slice(0, 120) } });
      if (!cursor) startNext();
      return ids.turnId;
    },

    setSpeed(next) {
      speed = next;
    },

    reset() {
      clear();
      cursor = null;
      queue.length = 0;
      buffered = [];
      online = true;
      runs.dispatch({ kind: 'reset' });
    },

    dispose() {
      clear();
      cursor = null;
    },
  };
}
