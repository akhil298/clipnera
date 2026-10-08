import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import './dev/resolve-hooks.mts';
import { baseTimeline } from './dev/fixture.mts';

const { createDocStore, selectItem, selectSaveState } = await import('./store.ts');
const { applyOps } = await import('./timeline.ts');

type Timeline = ReturnType<typeof baseTimeline>;
type Op = Parameters<typeof applyOps>[1][number];

const fail = (code: string, status: number) => Object.assign(new Error(code), { code, status });

/** A fake server holding the truth; `before` runs before each ops call (to move the server on). */
function fakeServer(start = baseTimeline()) {
  const server = { timeline: start, version: 1, calls: [] as { base: number; ops: Op[] }[], before: null as null | (() => void), error: null as null | Error };
  const transport = {
    async sendOps(_p: string, base: number, ops: Op[]) {
      server.calls.push({ base, ops });
      server.before?.();
      server.before = null;
      if (server.error) throw server.error;
      if (base !== server.version) throw fail('STALE_VERSION', 409);
      server.timeline = applyOps(server.timeline, ops);
      server.version += 1;
      return { timeline: server.timeline, version: server.version };
    },
    async fetchProject() {
      return { timeline: server.timeline, version: server.version };
    },
  };
  const commitRemote = (ops: Op[]) => {
    server.timeline = applyOps(server.timeline, ops);
    server.version += 1;
  };
  return { server, transport, commitRemote };
}

function memoryStorage() {
  const data = new Map<string, unknown[]>();
  return {
    data,
    async load(id: string) {
      return (data.get(id) ?? []) as never[];
    },
    async save(id: string, batches: unknown[]) {
      data.set(id, structuredClone(batches));
    },
  };
}

let ids = 0;
const newId = () => `b${++ids}`;
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const textOf = (t: Timeline | null) => {
  const item = t?.tracks.find((track) => track.id === 't1')?.items[0];
  return item?.type === 'text' ? item.text : undefined;
};

describe('doc store', () => {
  it('applies locally at once, sends, and acks', async () => {
    const { server, transport } = fakeServer();
    const doc = createDocStore({ transport, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    const result = doc.apply([{ op: 'update_item', item: 'h1', patch: { text: 'Hi' } }]);
    assert.equal(result.ok, true);
    assert.equal(textOf(doc.store.getState().view), 'Hi');
    assert.equal(selectSaveState(doc.store.getState()), 'saving');
    await doc.flush();
    const state = doc.store.getState();
    assert.equal(state.server!.version, 2);
    assert.equal(state.pending.length, 0);
    assert.equal(state.save, 'saved');
  });

  it('sends batches one at a time, each on the last acked version', async () => {
    const { server, transport } = fakeServer();
    const doc = createDocStore({ transport, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    doc.apply([{ op: 'move_item', item: 'b1', at: 100 }]);
    doc.apply([{ op: 'move_item', item: 'b1', at: 120 }]);
    await doc.flush();
    assert.deepEqual(server.calls.map((c) => c.base), [1, 2]);
    assert.equal(doc.store.getState().server!.version, 3);
  });

  it('rebases on 409 STALE_VERSION and keeps the edit', async () => {
    const { server, transport, commitRemote } = fakeServer();
    const doc = createDocStore({ transport, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    server.before = () => commitRemote([{ op: 'move_item', item: 'b1', at: 200 }]);
    doc.apply([{ op: 'update_item', item: 'h1', patch: { text: 'Mine' } }]);
    await doc.flush();
    const state = doc.store.getState();
    assert.equal(state.server!.version, 3);
    assert.equal(textOf(state.view), 'Mine');
    assert.equal(state.view!.tracks.find((t) => t.id === 'o1')!.items[0].at, 200);
    assert.deepEqual(state.dropped, []);
  });

  it('drops an edit the server change made impossible and reports it', async () => {
    const { server, transport, commitRemote } = fakeServer();
    const doc = createDocStore({ transport, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    server.before = () => commitRemote([{ op: 'remove_item', item: 'h1' }]);
    doc.apply([{ op: 'update_item', item: 'h1', patch: { text: 'Mine' } }], 'Title 2');
    await doc.flush();
    const state = doc.store.getState();
    assert.equal(state.pending.length, 0);
    assert.deepEqual(state.dropped.map((d) => [d.batch.label, d.code]), [['Title 2', 'UNKNOWN_ITEM']]);
    doc.dismissDropped(state.dropped[0].batch.id);
    assert.equal(doc.store.getState().dropped.length, 0);
  });

  it('goes offline on a network error, keeps the batch, and sends it on retry', async () => {
    const { server, transport } = fakeServer();
    const storage = memoryStorage();
    const doc = createDocStore({ transport, storage, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    server.error = fail('NETWORK', 0);
    doc.apply([{ op: 'move_item', item: 'b1', at: 100 }]);
    await doc.flush();
    assert.equal(doc.store.getState().save, 'offline');
    assert.equal(storage.data.get('p')!.length, 1);
    server.error = null;
    await doc.retry();
    assert.equal(doc.store.getState().save, 'saved');
    assert.equal(storage.data.get('p')!.length, 0);
  });

  it('restores unsent batches from storage on load and rebases them', async () => {
    const { server, transport } = fakeServer();
    const storage = memoryStorage();
    storage.data.set('p', [{ id: 'old', ops: [{ op: 'update_item', item: 'h1', patch: { text: 'Kept' } }], createdAt: 0 }]);
    const doc = createDocStore({ transport, storage, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    assert.equal(textOf(server.timeline), 'Kept');
    assert.equal(doc.store.getState().pending.length, 0);
  });

  it('drops a batch the server refuses', async () => {
    const { server, transport } = fakeServer();
    const doc = createDocStore({ transport, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    server.error = fail('OVERLAP', 400);
    doc.apply([{ op: 'move_item', item: 'b1', at: 100 }]);
    await doc.flush();
    const state = doc.store.getState();
    assert.equal(state.pending.length, 0);
    assert.equal(state.dropped[0].code, 'OVERLAP');
    assert.equal(state.view!.tracks.find((t) => t.id === 'o1')!.items[0].at, 90);
  });

  it('refuses edits on locked items, invalid edits, and while viewing an old version', async () => {
    const { server, transport } = fakeServer();
    const doc = createDocStore({ transport, newId, isLocked: (id) => id === 'c1' });
    assert.equal((doc.apply([{ op: 'remove_item', item: 'c2' }]) as { code: string }).code, 'NOT_READY');
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    assert.deepEqual(doc.apply([{ op: 'remove_item', item: 'c1' }]), {
      ok: false, code: 'LOCKED', message: 'Clipnera is working on this. It unlocks when the step ends.', itemIds: ['c1'],
    });
    assert.equal((doc.apply([{ op: 'move_item', item: 'b1', at: 100, track: 'v1' }]) as { code: string }).code, 'OVERLAP');
    doc.viewVersion('v9', 'Trimmed silences', baseTimeline());
    assert.equal((doc.apply([{ op: 'remove_item', item: 'c2' }]) as { code: string }).code, 'READ_ONLY');
    doc.backToLatest();
    assert.equal(doc.apply([{ op: 'remove_item', item: 'c2' }]).ok, true);
    await doc.flush();
  });

  it('applies remote revisions in order, ignores duplicates, and resyncs on a gap', async () => {
    const { server, transport, commitRemote } = fakeServer();
    const doc = createDocStore({ transport, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    const untouched = selectItem('c1')(doc.store.getState());
    const ops: Op[] = [{ op: 'move_item', item: 'b1', at: 200 }];
    commitRemote(ops);
    await doc.applyRemote({ base_revision: 1, revision: 2, ops, item_ids: ['b1'], changed_ranges: [[200, 260]] });
    let state = doc.store.getState();
    assert.equal(state.server!.version, 2);
    assert.deepEqual(state.landed?.itemIds, ['b1']);
    assert.equal(selectItem('c1')(state), untouched, 'untouched items keep their identity');
    await doc.applyRemote({ base_revision: 1, revision: 2, ops });
    assert.equal(doc.store.getState().server!.version, 2);
    commitRemote([{ op: 'move_item', item: 'b1', at: 210 }]);
    commitRemote([{ op: 'move_item', item: 'b1', at: 220 }]);
    await doc.applyRemote({ base_revision: 3, revision: 4, ops: [{ op: 'move_item', item: 'b1', at: 220 }] });
    state = doc.store.getState();
    assert.equal(state.server!.version, 4);
    assert.equal(state.view!.tracks.find((t) => t.id === 'o1')!.items[0].at, 220);
  });

  it('keeps pending edits on top of a remote revision', async () => {
    const { server, transport } = fakeServer();
    server.error = fail('NETWORK', 0);
    const doc = createDocStore({ transport, newId });
    await doc.hydrate('p', { timeline: server.timeline, version: 1 });
    doc.apply([{ op: 'update_item', item: 'h1', patch: { text: 'Mine' } }]);
    await settle();
    await doc.applyRemote({ base_revision: 1, revision: 2, ops: [{ op: 'move_item', item: 'b1', at: 200 }] });
    const state = doc.store.getState();
    assert.equal(textOf(state.view), 'Mine');
    assert.equal(textOf(state.server!.timeline), 'Nobody tells you this');
  });
});
