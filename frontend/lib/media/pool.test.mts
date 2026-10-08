import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { TrackPool, type MediaElementLike } from './pool.ts';

class FakeElement implements MediaElementLike {
  src = '';
  currentTime = 0;
  playbackRate = 1;
  muted = false;
  volume = 1;
  paused = true;
  readyState = 4;
  visible = false;
  frameCallbacks: Array<() => void> = [];
  listeners = new Map<string, () => void>();
  play() { this.paused = false; }
  pause() { this.paused = true; }
  removeAttribute() { this.src = ''; }
  load() {}
  addEventListener(type: string, fn: () => void) { this.listeners.set(type, fn); }
  removeEventListener(type: string) { this.listeners.delete(type); }
  requestVideoFrameCallback = (cb: () => void) => { this.frameCallbacks.push(cb); return 1; };
}

function setup() {
  const errors: Array<[string, string]> = [];
  const pool = new TrackPool<FakeElement>({
    create: () => new FakeElement(),
    setVisible: (el, visible) => (el.visible = visible),
    onError: (key, url) => errors.push([key, url]),
  });
  const [a, b] = pool.elements as FakeElement[];
  return { pool, a, b, errors };
}

const target = (key: string, sourceTime = 0) => ({ key, url: `u/${key}`, sourceTime, rate: 1, gain: 1 });

describe('A/B track pool', () => {
  it('plays the current item and preloads the next into the hidden element', () => {
    const { pool, a, b } = setup();
    pool.show(target('c1', 1), true);
    assert.deepEqual([a.src, a.currentTime, a.paused, a.visible], ['u/c1', 1, false, true]);
    pool.preload({ key: 'c2', url: 'u/c2', sourceTime: 4 });
    assert.deepEqual([b.src, b.currentTime, b.paused, b.visible], ['u/c2', 4, true, false]);
  });

  it('swaps at the cut and hides the old element once the new one has painted', () => {
    const { pool, a, b } = setup();
    pool.show(target('c1'), true);
    pool.preload({ key: 'c2', url: 'u/c2', sourceTime: 4 });
    pool.show(target('c2', 4), true);
    assert.equal(pool.current, b);
    assert.deepEqual([b.visible, b.paused, a.visible], [true, false, true], 'old frame stays up until the new one paints');
    b.frameCallbacks.forEach((cb) => cb());
    assert.deepEqual([a.visible, a.paused], [false, true]);
  });

  it('only re-seeks past the drift allowance while playing, exactly when paused', () => {
    const { pool, a } = setup();
    pool.show(target('c1', 1), true);
    a.currentTime = 1.1;
    pool.show(target('c1', 1.2), true);
    assert.equal(a.currentTime, 1.1);
    pool.show(target('c1', 1.2), false);
    assert.deepEqual([a.currentTime, a.paused], [1.2, true]);
  });

  it('reports errors with the failing URL and reloads a fresh one in place', () => {
    const { pool, a, errors } = setup();
    pool.show(target('c1', 2), true);
    a.listeners.get('error')!();
    assert.deepEqual(errors, [['c1', 'u/c1']]);
    a.currentTime = 2.5;
    pool.replaceUrl('c1', 'u/c1?fresh');
    assert.deepEqual([a.src, a.currentTime, a.paused], ['u/c1?fresh', 2.5, false]);
  });

  it('is stalled while the visible element lacks data', () => {
    const { pool, a } = setup();
    pool.show(target('c1'), true);
    a.readyState = 2;
    assert.equal(pool.stalled, true);
    pool.show(null, true);
    assert.equal(pool.stalled, false);
    assert.equal(a.visible, false);
  });
});
