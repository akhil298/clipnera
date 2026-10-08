import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import './dev/resolve-hooks.mts';

const { createSelectionStore, chipsFor, toWireChip, toContext, contextFromWire, reduceSelect, selectionKey } = await import('./selection.ts');

type Sel = Parameters<typeof selectionKey>[0];
const item: Sel = { kind: 'item', itemId: 'c3', label: '03 · Hot take', meta: '7s' };
const range: Sel = { kind: 'range', start: 360, end: 930 };

describe('selection', () => {
  it('replaces, adds with ⌘-click, and toggles off', () => {
    assert.deepEqual(reduceSelect([item], range, false), [range]);
    assert.deepEqual(reduceSelect([item], range, true), [item, range]);
    assert.deepEqual(reduceSelect([item, range], item, true), [range]);
  });

  it('makes composer chips, locked while a step holds the item', () => {
    const chips = chipsFor([item, range, { kind: 'caption', start: 0, end: 30, text: 'most people never tell you this one simple thing about pricing' }, { kind: 'region', frame: 420, bbox: { x: 0.1, y: 0.1, w: 0.5, h: 0.5 } }], 30, (id) => id === 'c3');
    assert.deepEqual(
      chips.map((c) => [c.kind, c.label, c.locked]),
      [
        ['clip', '03 · Hot take', true],
        ['range', '0:12 – 0:31', false],
        ['caption', '“most people never tell you this one simp…”', false],
        ['moment', 'Area at 0:14', false],
      ],
    );
  });

  it('maps to the wire chip for POST /runs', () => {
    assert.deepEqual(toWireChip(item, 30), { type: 'clip', ref: { item_id: 'c3' }, label: '03 · Hot take' });
    assert.deepEqual(toWireChip(range, 30), { type: 'range', ref: { start_frame: 360, end_frame: 930 }, label: '0:12 – 0:31' });
    assert.deepEqual(toWireChip({ kind: 'asset', assetId: 'b9', library: 'broll', label: 'Coffee' }, 30).ref, { broll_asset_id: 'b9' });
    assert.deepEqual(toWireChip({ kind: 'moment', frame: 630 }, 30), { type: 'moment', ref: { frame: 630 }, label: '0:21' });
  });

  it('reads server chips back for the turn heading', () => {
    const ctx = contextFromWire({ type: 'caption_line', ref: { start_frame: 0, end_frame: 30 }, label: '“so”' });
    assert.equal(ctx.kind, 'caption');
    assert.equal(ctx.label, '“so”');
    assert.equal(toContext(item, 30).id, 'item:c3');
  });

  it('store: select, remove, prune, clear', () => {
    const sel = createSelectionStore();
    sel.select(item);
    sel.select(range, { additive: true });
    assert.equal(sel.store.getState().selected.length, 2);
    sel.remove(selectionKey(range));
    sel.prune((id) => id !== 'c3');
    assert.deepEqual(sel.store.getState().selected, []);
    sel.select(range);
    sel.clear();
    assert.deepEqual(sel.store.getState().selected, []);
  });
});
