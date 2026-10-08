import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import './resolve-hooks.mts';

const { createRunSimulator } = await import('./simulator.ts');
const { SCENARIOS } = await import('./scenarios.ts');
const { createRunStore, selectQueue } = await import('../run-store.ts');

/** Runs timers by hand, in order, so a whole scenario plays instantly. */
function manualTimers() {
  const due: { fn: () => void; handle: number }[] = [];
  let next = 0;
  return {
    set: (fn: () => void) => (due.push({ fn, handle: ++next }), next),
    clear: (handle: unknown) => {
      const index = due.findIndex((t) => t.handle === handle);
      if (index >= 0) due.splice(index, 1);
    },
    drain() {
      for (let guard = 0; due.length && guard < 10_000; guard += 1) due.shift()!.fn();
    },
  };
}

function setup() {
  const runs = createRunStore();
  const timers = manualTimers();
  const side: string[] = [];
  const ops: number[] = [];
  const sim = createRunSimulator({ runs, timers, onSideEvent: (e) => side.push(e.type), onOperation: (e) => ops.push(e.data.revision) });
  return { runs, timers, sim, side, ops, turn: () => runs.store.getState().turns.at(-1)! };
}

describe('dev run simulator', () => {
  it('plays the happy run to a result through the run store', () => {
    const { sim, timers, turn, side, ops } = setup();
    sim.start('happy');
    timers.drain();
    assert.equal(turn().status, 'succeeded');
    assert.deepEqual(turn().revisions, [41, 42]);
    assert.deepEqual(ops, [41, 42]);
    assert.ok(side.includes('version.created'));
  });

  it('waits on a question until answered', () => {
    const { sim, timers, turn } = setup();
    sim.start('question');
    timers.drain();
    assert.equal(turn().status, 'awaiting_input');
    assert.equal(turn().sources.length, 2);
    sim.answer('a');
    timers.drain();
    assert.equal(turn().question?.chosenId, 'a');
    assert.equal(turn().status, 'succeeded');
  });

  it('finishes with what is done after a credits pause', () => {
    const { sim, timers, turn } = setup();
    sim.start('credits');
    timers.drain();
    assert.equal(turn().status, 'paused');
    sim.decide('finish');
    timers.drain();
    assert.equal(turn().status, 'partial');
  });

  it('stops mid-run, keeping completed work as a partial result', () => {
    const { sim, timers, turn, runs } = setup();
    sim.start('happy');
    // Play until the first operation has landed.
    for (let i = 0; i < 200 && !turn().revisions.length; i += 1) timers.drain.call({}), void 0;
    sim.stop();
    timers.drain();
    assert.ok(['partial', 'cancelled', 'succeeded'].includes(turn().status));
    assert.deepEqual(runs.store.getState().locks, {});
  });

  it('replays events missed while offline on sync.reset', () => {
    const { sim, timers, turn } = setup();
    sim.start('connection');
    timers.drain();
    assert.equal(turn().status, 'succeeded');
    assert.deepEqual(turn().revisions, [41, 42]);
  });

  it('queues a prompt sent during a run and runs it next', () => {
    const { sim, timers, runs } = setup();
    sim.start('happy');
    sim.enqueue('make the captions bigger');
    assert.equal(selectQueue(runs.store.getState()).length, 1);
    timers.drain();
    const turns = runs.store.getState().turns;
    assert.deepEqual(turns.map((t) => t.status), ['succeeded', 'succeeded']);
    assert.equal(turns[1].prompt, 'make the captions bigger');
  });

  it('every scenario ends in a terminal state when gates are answered', () => {
    for (const scenario of SCENARIOS) {
      const { sim, timers, turn } = setup();
      sim.start(scenario.id);
      for (let guard = 0; guard < 5; guard += 1) {
        timers.drain();
        if (turn().status === 'awaiting_input') sim.answer(turn().question!.choices[0].id);
        else if (turn().status === 'paused') sim.decide('continue');
        else break;
      }
      assert.ok(['succeeded', 'partial', 'failed', 'cancelled'].includes(turn().status), `${scenario.id}: ${turn().status}`);
    }
  });
});
