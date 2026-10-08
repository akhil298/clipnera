import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import './dev/resolve-hooks.mts';

const rs = await import('./run-store.ts');
const { reduceRun, INITIAL_RUN_STATE, selectActiveTurn, selectQueue, selectIsLocked } = rs;

type State = typeof INITIAL_RUN_STATE;
type Event = Extract<Parameters<typeof reduceRun>[1], { kind: 'event' }>['event'];

const credits = { estimate: 4, held: 4, spent: 0 };
let seq = 0;
const ev = (type: string, data: object, extra: Partial<{ seq: number; durable: boolean; run_id: string }> = {}): Event =>
  ({ type, data, run_id: 'r1', seq: extra.seq ?? ++seq, durable: extra.durable ?? true, ...extra }) as Event;
const live = (type: string, data: object, at: number): Event => ({ type, data, run_id: 'r1', seq: at, durable: false }) as Event;
const play = (state: State, ...events: Event[]) => events.reduce((s, event) => reduceRun(s, { kind: 'event', event }), state);

function sent(): State {
  seq = 0;
  let s = reduceRun(INITIAL_RUN_STATE, { kind: 'send', turnId: 't1', prompt: 'trim silences', chips: [], mode: 'edit', at: Date.parse('2026-10-08T00:00:00Z') });
  s = reduceRun(s, {
    kind: 'bind',
    turnId: 't1',
    run: { id: 'r1', project_id: 'p', status: 'acknowledged', mode: 'edit', prompt: 'trim silences', credits, last_event_seq: 0, created_at: '2026-10-08T00:00:00Z' },
  });
  return s;
}

const ack = () => ev('run.acknowledged', { status: 'acknowledged', mode: 'edit', chips: [{ type: 'clip', ref: { item_id: 'c1' }, label: 'Hot take' }], base_revision: 40, credits });
const plan = () => ev('run.plan', { sentences: ['I will trim.'], steps: [{ id: 's1', label: 'Finding silences' }, { id: 's2', label: 'Trimming' }], credits, needs_approval: false });

describe('run store: a whole run', () => {
  it('builds the turn from plan, steps, locks, operations, check and result', () => {
    let s = sent();
    assert.equal(s.turns[0].status, 'acknowledged');
    s = play(s, ack(), live('run.plan.delta', { text: 'I will ' }, 1), live('run.plan.delta', { text: 'trim.' }, 1));
    assert.equal(s.turns[0].planText, 'I will trim.');
    assert.equal(s.turns[0].status, 'planning');
    s = play(s, plan(), ev('run.step.started', { step_id: 's1', index: 1, total: 2, label: 'Finding silences' }));
    assert.deepEqual(s.turns[0].steps.map((x) => x.status), ['active', 'queued']);
    s = play(s, live('run.step.progress', { step_id: 's1', done: 6, total: 14 }, seq));
    assert.equal(s.turns[0].steps[0].progress, '6 of 14');
    s = play(
      s,
      ev('run.step.completed', { step_id: 's1', label: 'Finding silences', summary: 'Found 14', revisions: [] }),
      ev('run.step.started', { step_id: 's2', index: 2, total: 2, label: 'Trimming' }),
      ev('run.lock.acquired', { step_id: 's2', item_ids: ['c1', 'c2'] }),
    );
    assert.equal(selectIsLocked('c1')(s), true);
    s = play(s, ev('run.operation.applied', { revision: 41, base_revision: 40, ops: [], changed_ranges: [[0, 30]], item_ids: ['c1'], step_id: 's2', client_batch_id: 'x' }));
    assert.deepEqual(s.turns[0].revisions, [41]);
    assert.deepEqual(s.markers.c1, { turnId: 't1', runId: 'r1', revision: 41 });
    s = play(
      s,
      ev('run.lock.released', { step_id: 's2', item_ids: ['c1', 'c2'] }),
      ev('run.step.completed', { step_id: 's2', label: 'Trimming', summary: 'Removed 42 s', revisions: [41] }),
      ev('run.check.started', {}),
    );
    assert.equal(selectIsLocked('c1')(s), false);
    assert.equal(s.turns[0].status, 'checking');
    s = play(
      s,
      ev('run.check.completed', { passed: true, findings: [] }),
      ev('run.result', {
        status: 'succeeded', version: { id: 'v42', name: 'Trimmed', result_revision: 41 }, summary: { done: ['Removed 42 s'], not_done: [] },
        suggestions: [], credits: { ...credits, spent: 4 }, duration_ms: 1000, citations: [{ id: 'c1', start_f: 0, end_f: 30, text: 'so' }],
      }),
    );
    const turn = s.turns[0];
    assert.equal(turn.status, 'succeeded');
    assert.equal(turn.result?.version?.name, 'Trimmed');
    assert.equal(turn.citations.length, 1);
    assert.deepEqual(turn.steps.map((x) => x.status), ['done', 'done', 'done']);
    assert.equal(selectActiveTurn(s), undefined);
  });
});

describe('run store: ordering (events.md §7.3)', () => {
  it('drops duplicates and stale ephemeral events', () => {
    let s = play(sent(), ack(), plan());
    const again = play(s, ev('run.plan', { sentences: ['Other'], steps: [], credits, needs_approval: false }, { seq: 2 }));
    assert.equal(again, s);
    s = play(s, live('run.plan.delta', { text: 'late' }, 1));
    assert.equal(s.turns[0].planText, 'I will trim.');
  });

  it('buffers past a gap, asks for a backfill, and drains in order', () => {
    let s = play(sent(), ack());
    const step2 = ev('run.step.started', { step_id: 's1', index: 1, total: 2, label: 'Finding silences' }, { seq: 3 });
    s = play(s, step2);
    assert.deepEqual(s.backfill, { r1: 1 });
    assert.equal(s.turns[0].steps.length, 0);
    s = play(s, ev('run.plan', { sentences: ['I will trim.'], steps: [{ id: 's1', label: 'Finding silences' }], credits, needs_approval: false }, { seq: 2 }));
    assert.deepEqual(s.backfill, {});
    assert.equal(s.lastSeq.r1, 3);
    assert.equal(s.turns[0].steps[0].status, 'active');
  });

  it('starts a turn from the stream when it outruns POST /runs, then merges on bind', () => {
    seq = 0;
    let s = reduceRun(INITIAL_RUN_STATE, { kind: 'send', turnId: 'local', prompt: 'hello', chips: [], mode: 'edit', at: 1 });
    s = play(s, ack(), plan());
    assert.equal(s.turns.length, 2);
    s = reduceRun(s, { kind: 'bind', turnId: 'local', run: { id: 'r1', project_id: 'p', status: 'planning', mode: 'edit', prompt: 'hello', credits, last_event_seq: 2, created_at: '2026-10-08T00:00:00Z' } });
    assert.equal(s.turns.length, 1);
    assert.equal(s.turns[0].id, 'local');
    assert.equal(s.turns[0].prompt, 'hello');
    assert.equal(s.turns[0].plan?.steps.length, 2);
  });
});

describe('run store: questions, pauses, stop, failures', () => {
  it('records a pick optimistically and when confirmed', () => {
    let s = play(sent(), ack(), ev('run.question', { question_id: 'q1', text: 'Which?', choices: [{ id: 'a', label: 'A' }], allow_skip: true }));
    assert.equal(s.turns[0].status, 'awaiting_input');
    s = reduceRun(s, { kind: 'answer', runId: 'r1', choiceId: 'a' });
    assert.equal(s.turns[0].question?.chosenId, 'a');
    s = play(s, ev('run.answered', { question_id: 'q1', choice_id: 'a', skipped: false, by: 'user' }));
    assert.equal(s.turns[0].status, 'planning');
  });

  it('pauses and resumes', () => {
    let s = play(sent(), ack(), ev('run.paused', { reason: 'credits', credits, needed: 3, options: ['add_credits', 'finish'] }));
    assert.equal(s.turns[0].status, 'paused');
    s = reduceRun(s, { kind: 'decide', runId: 'r1', decision: 'add_credits' });
    assert.equal(s.turns[0].pause?.decided, 'add_credits');
    s = play(s, ev('run.resumed', { reason: 'credits_added' }));
    assert.equal(s.turns[0].pause, undefined);
  });

  it('stops: queued steps are skipped and locks released', () => {
    let s = play(sent(), ack(), plan(), ev('run.step.started', { step_id: 's1', index: 1, total: 2, label: 'Finding silences' }), ev('run.lock.acquired', { step_id: 's1', item_ids: ['c1'] }));
    s = reduceRun(s, { kind: 'stop', runId: 'r1' });
    assert.equal(s.turns[0].status, 'stopping');
    s = play(s, ev('run.cancelled', { by: 'user', while: 'running' }));
    assert.equal(s.turns[0].status, 'cancelled');
    assert.equal(s.turns[0].steps[1].status, 'skipped');
    assert.deepEqual(s.locks, {});
  });

  it('retries a step, then fails the run with its kept version', () => {
    let s = play(sent(), ack(), plan(), ev('run.step.started', { step_id: 's1', index: 1, total: 2, label: 'Finding silences' }));
    const error = { code: 'X', message: 'It broke.', retryable: true };
    s = play(s, ev('run.step.failed', { step_id: 's1', error, will_retry: true, attempt: 1 }));
    assert.equal(s.turns[0].steps[0].progress, 'Trying again');
    s = play(s, ev('run.step.failed', { step_id: 's1', error, will_retry: false, attempt: 2 }), ev('run.failed', { error, version: { id: 'v41', name: 'Trimmed' }, credits }));
    assert.equal(s.turns[0].status, 'failed');
    assert.equal(s.turns[0].failure?.version?.id, 'v41');
    assert.equal(s.turns[0].steps[0].status, 'failed');
  });
});

describe('run store: queue, markers, hydrate', () => {
  it('lists queued prompts in order and keeps the selector stable', () => {
    seq = 0;
    let s = INITIAL_RUN_STATE;
    for (const [id, pos] of [['a', 2], ['b', 1]] as const) {
      s = reduceRun(s, { kind: 'send', turnId: id, prompt: id, chips: [], mode: 'edit', at: 1 });
      s = reduceRun(s, { kind: 'bind', turnId: id, run: { id, project_id: 'p', status: 'queued', mode: 'edit', prompt: id, queue_position: pos, credits, last_event_seq: 1, created_at: '2026-10-08T00:00:00Z' } });
    }
    assert.deepEqual(selectQueue(s).map((t) => t.id), ['b', 'a']);
    assert.equal(selectQueue(s), selectQueue({ ...s, locks: {} }));
    s = reduceRun(s, { kind: 'remove', turnId: 'b' });
    assert.deepEqual(selectQueue(s).map((t) => t.id), ['a']);
  });

  it('clears markers on a hand edit and when the next run starts', () => {
    let s = play(sent(), ack(), ev('run.operation.applied', { revision: 41, base_revision: 40, ops: [], changed_ranges: [], item_ids: ['c1', 'c2'], step_id: 's1', client_batch_id: 'x' }));
    s = reduceRun(s, { kind: 'markers.clear', itemIds: ['c1'] });
    assert.deepEqual(Object.keys(s.markers), ['c2']);
    s = play(s, { ...ack(), run_id: 'r2', seq: 1 } as Event);
    assert.deepEqual(s.markers, {});
  });

  it('rebuilds older turns from run snapshots', () => {
    const s = reduceRun(sent(), {
      kind: 'hydrate',
      runs: [{
        id: 'old', project_id: 'p', status: 'succeeded', mode: 'ask', prompt: 'where?', credits, last_event_seq: 9,
        created_at: '2026-10-01T00:00:00Z', started_at: '2026-10-01T00:00:00Z', summary: { done: [], not_done: [], answer: 'At 0:12.' },
      }],
    });
    assert.deepEqual(s.turns.map((t) => t.id), ['old', 't1']);
    assert.equal(s.turns[0].answerText, 'At 0:12.');
    assert.equal(s.turns[0].result?.status, 'succeeded');
    assert.equal(s.lastSeq.old, 9);
  });
});
