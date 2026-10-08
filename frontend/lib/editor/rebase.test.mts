import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import './dev/resolve-hooks.mts';
import { baseTimeline } from './dev/fixture.mts';

const { rebase, fitRemote, batchItemIds, shareUnchanged } = await import('./rebase.ts');
const { applyOps } = await import('./timeline.ts');

const batch = (id: string, ops: unknown[]) => ({ id, ops: ops as never, createdAt: 0 });

describe('rebase', () => {
  it('re-applies pending batches on a new server document', () => {
    const server = applyOps(baseTimeline(), [{ op: 'move_item', item: 'b1', at: 200 }]);
    const result = rebase(server, [batch('p1', [{ op: 'update_item', item: 'h1', patch: { text: 'Hello' } }])]);
    assert.equal(result.kept.length, 1);
    assert.equal(result.dropped.length, 0);
    const text = result.view.tracks.find((t) => t.id === 't1')!.items[0];
    assert.equal(text.type === 'text' && text.text, 'Hello');
    assert.equal(result.view.tracks.find((t) => t.id === 'o1')!.items[0].at, 200);
  });

  it('drops a batch that no longer applies and keeps the rest', () => {
    const server = applyOps(baseTimeline(), [{ op: 'remove_item', item: 'h1' }]);
    const result = rebase(server, [
      batch('gone', [{ op: 'update_item', item: 'h1', patch: { text: 'Hello' } }]),
      batch('fine', [{ op: 'move_item', item: 'b1', at: 30 }]),
    ]);
    assert.deepEqual(result.kept.map((b) => b.id), ['fine']);
    assert.deepEqual(result.dropped.map((d) => [d.batch.id, d.code]), [['gone', 'UNKNOWN_ITEM']]);
  });

  it('classifies remote revisions', () => {
    assert.equal(fitRemote(41, 40, 41), 'duplicate');
    assert.equal(fitRemote(41, 41, 42), 'next');
    assert.equal(fitRemote(41, 43, 44), 'gap');
  });

  it('names the items a batch touches', () => {
    assert.deepEqual(
      batchItemIds([{ op: 'split_item', item: 'c1', at: 100, new_id: 'c1b' }, { op: 'remove_item', item: 'c1b' }, { op: 'set_captions', enabled: false }]),
      ['c1', 'c1b'],
    );
  });
});

describe('shareUnchanged', () => {
  it('keeps the identity of untouched items and tracks', () => {
    const prev = baseTimeline();
    const next = applyOps(prev, [{ op: 'move_item', item: 'b1', at: 200 }]);
    const shared = shareUnchanged(prev, next);
    assert.equal(shared.tracks[0], prev.tracks[0]);
    assert.equal(shared.tracks[2].items[0], prev.tracks[2].items[0]);
    assert.notEqual(shared.tracks[1], prev.tracks[1]);
    assert.equal(shared.assets, prev.assets);
    assert.deepEqual(shared, next);
  });

  it('returns the previous document when nothing changed', () => {
    const prev = baseTimeline();
    assert.equal(shareUnchanged(prev, structuredClone(prev)), prev);
  });
});
