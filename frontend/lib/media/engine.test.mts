import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import './testing/resolve-ts.mts';
import { timeline } from './testing/fixtures.mts';
import type { Scheduler } from '../editor/playback/clock.ts';

const { PreviewEngine } = await import('./engine.ts');

/** Just enough of a media/img element for the engine. */
class FakeNode {
  kind: string;
  src = '';
  currentTime = 0;
  playbackRate = 1;
  muted = false;
  volume = 1;
  paused = true;
  readyState = 4;
  style: Record<string, string> = {};
  dataset: Record<string, string> = {};
  attrs = new Map<string, string>();
  listeners = new Map<string, () => void>();
  constructor(kind: string) { this.kind = kind; }
  play() { this.paused = false; return Promise.resolve(); }
  pause() { this.paused = true; }
  load() {}
  remove() {}
  setAttribute(k: string, v: string) { this.attrs.set(k, v); }
  getAttribute(k: string) { return k === 'src' ? this.src : this.attrs.get(k) ?? null; }
  removeAttribute() { this.src = ''; }
  addEventListener(type: string, fn: () => void) { this.listeners.set(type, fn); }
  removeEventListener(type: string) { this.listeners.delete(type); }
}

async function setup(resolve: (key: string, refresh: boolean) => string = (key) => `https://cdn/${key}`) {
  let now = 0;
  let pending: ((n: number) => void) | null = null;
  const scheduler: Scheduler = { now: () => now, request: (cb) => { pending = cb; return 1; }, cancel: () => { pending = null; } };
  const nodes: FakeNode[] = [];
  const engine = new PreviewEngine({
    timeline,
    resolveUrl: async (ref, { refresh }) => resolve(ref.kind === 'asset' ? ref.asset.id : ref.kind === 'music' ? ref.track : ref.name, refresh),
    scheduler,
    document: null,
    matchMedia: null,
    createElement: (kind) => { const n = new FakeNode(kind); nodes.push(n); return n as unknown as HTMLElement; },
  });
  await new Promise((r) => setImmediate(r));
  const advance = (ms: number) => { now += ms; const cb = pending; pending = null; cb?.(now); };
  const visible = (kind: string) => nodes.filter((n) => n.kind === kind && n.style.visibility === 'visible');
  return { engine, nodes, advance, visible };
}

describe('preview engine', () => {
  it('shows the picture at the clock position and keeps audio in step', async () => {
    const { engine, visible, nodes } = await setup();
    assert.equal(engine.clock.getState().duration, 5);
    engine.seek(1);
    const [video] = visible('video');
    assert.equal(video.src, 'https://cdn/a');
    assert.equal(video.currentTime, 2);
    assert.equal(visible('img')[0].src, 'https://cdn/img', 'B-roll image is up');
    const voice = nodes.find((n) => n.kind === 'audio' && n.src === 'https://cdn/vo')!;
    assert.equal(voice.currentTime, 1);
    assert.equal(voice.volume, 0.8);
  });

  it('preloads the next clip and fires sound effects while playing', async () => {
    const { engine, nodes, advance } = await setup();
    const cues: string[] = [];
    engine.on((e) => { if (e.type === 'cue') cues.push(e.sfx.name); });
    engine.seek(2.6);
    assert.ok(nodes.some((n) => n.kind === 'video' && n.src === 'https://cdn/b' && n.paused), 'c2 waits in the standby element');
    engine.seek(1.4);
    engine.play();
    advance(200);
    assert.deepEqual(cues, ['whoosh']);
  });

  it('refreshes an expired link in place and reports a source that never plays', async () => {
    let version = 0;
    const { engine, visible } = await setup((key, refresh) => `https://cdn/${key}?v=${refresh ? ++version : 0}`);
    const errors: string[] = [];
    engine.on((e) => { if (e.type === 'media-error' || e.type === 'url-refreshed') errors.push(e.type); });
    engine.seek(0.5);
    const video = visible('video')[0];
    video.listeners.get('error')!();
    await new Promise((r) => setImmediate(r));
    assert.equal(video.src, 'https://cdn/a?v=1');
    assert.equal(video.currentTime, 1.5, 'same position');
    video.listeners.get('error')!();
    await new Promise((r) => setImmediate(r));
    video.listeners.get('error')!();
    await new Promise((r) => setImmediate(r));
    assert.deepEqual(errors, ['url-refreshed', 'url-refreshed', 'media-error']);
  });

  it('keeps the playhead when the edit changes', async () => {
    const { engine } = await setup();
    engine.seek(2);
    engine.setTimeline({ ...timeline, look: 'vivid' });
    assert.equal(engine.clock.time, 2);
    engine.destroy();
  });
});
