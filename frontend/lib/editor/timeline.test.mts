// Runs the backend's shared fixtures through the browser applier: `npm test`.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import { applyOps, duration, normalise, TimelineError, toFrames, type TimelineOp } from './timeline.ts';

interface Case {
  name: string;
  ops: TimelineOp[];
  expect: { timeline: unknown } | { error: string; op_index: number };
}

const fixtures = JSON.parse(
  readFileSync(new URL('../../../backend/editor/fixtures/timeline_ops.json', import.meta.url), 'utf8'),
) as { base: unknown; cases: Case[] };
const base = normalise(fixtures.base);

describe('shared timeline fixtures', () => {
  for (const c of fixtures.cases) {
    it(c.name, () => {
      if ('error' in c.expect) {
        const { error, op_index } = c.expect;
        assert.throws(() => applyOps(base, c.ops), (e: unknown) => {
          assert.ok(e instanceof TimelineError);
          assert.deepEqual([e.code, e.opIndex], [error, op_index]);
          return true;
        });
      } else {
        assert.deepEqual(applyOps(base, c.ops), normalise(c.expect.timeline));
      }
    });
  }
});

describe('timeline helpers', () => {
  it('leaves the input alone', () => {
    const before = structuredClone(base);
    applyOps(base, [{ op: 'remove_item', item: 'c1', ripple: true }]);
    assert.deepEqual(base, before);
  });

  it('rounds half up, like the backend', () => {
    assert.deepEqual([0.5, 1.5, 2.5, 2.49].map(toFrames), [1, 2, 3, 2]);
  });

  it('measures the base timeline', () => {
    assert.equal(duration(base), 450);
  });
});
