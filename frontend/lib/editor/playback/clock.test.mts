import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { frameAt, PlaybackClock, skipForward, type ClockEvent, type Scheduler } from './clock.ts';

/** A hand-cranked animation frame source. */
function fakeScheduler() {
  let now = 0;
  let pending: ((now: number) => void) | null = null;
  const scheduler: Scheduler = {
    now: () => now,
    request: (cb) => { pending = cb; return 1; },
    cancel: () => { pending = null; },
  };
  const advance = (ms: number, frames = 1) => {
    for (let i = 0; i < frames; i++) {
      now += ms / frames;
      const cb = pending;
      pending = null;
      cb?.(now);
    }
  };
  return { scheduler, advance, get running() { return pending !== null; } };
}

const setup = (duration = 10) => {
  const s = fakeScheduler();
  const clock = new PlaybackClock({ fps: 30, duration, scheduler: s.scheduler });
  const events: ClockEvent[] = [];
  clock.on((e) => events.push(e));
  return { clock, events, ...s };
};

describe('playback clock', () => {
  it('advances with wall time and rate, without accumulating drift', () => {
    const { clock, advance } = setup();
    clock.play();
    advance(1000, 60);
    assert.ok(Math.abs(clock.time - 1) < 1e-9);
    clock.setRate(2);
    advance(500, 7);
    assert.ok(Math.abs(clock.time - 2) < 1e-9);
    assert.equal(clock.getState().frame, 60);
  });

  it('stops at the end, and play restarts from the top', () => {
    const { clock, events, advance, running } = setup(1);
    clock.play();
    advance(1500);
    assert.deepEqual([clock.time, clock.getState().playing, clock.getState().ended], [1, false, true]);
    assert.equal(running, false);
    assert.deepEqual(events.slice(-2).map((e) => e.type), ['pause', 'ended']);
    clock.play();
    assert.equal(clock.time, 0);
  });

  it('loops a range', () => {
    const { clock, events, advance } = setup();
    clock.setLoop({ start: 2, end: 3 });
    clock.play();
    assert.equal(clock.time, 2, 'playing outside the loop starts at its start');
    advance(1100);
    assert.equal(clock.time, 2);
    assert.ok(events.some((e) => e.type === 'loop'));
  });

  it('steps whole frames and clamps to the last frame', () => {
    const { clock } = setup(1);
    clock.step(1);
    assert.equal(clock.getState().frame, 1);
    clock.step(100);
    assert.equal(clock.getState().frame, 29);
    clock.step(-5);
    assert.equal(clock.getState().frame, 24);
    assert.equal(frameAt(24 / 30, 30), 24, 'frame times land on their own frame');
  });

  it('jumps over skipped ranges while playing', () => {
    const { clock, advance } = setup();
    clock.setSkips([{ start: 0.5, end: 2 }]);
    clock.play();
    advance(600);
    assert.ok(Math.abs(clock.time - 2) < 1e-9);
    advance(100);
    assert.ok(Math.abs(clock.time - 2.1) < 1e-9);
    assert.equal(skipForward(1, [{ start: 0, end: 2 }, { start: 2, end: 3 }]), 3);
  });

  it('holds still while buffering', () => {
    const { clock, advance } = setup();
    clock.play();
    advance(100);
    clock.setBuffering(true);
    advance(500);
    assert.ok(Math.abs(clock.time - 0.1) < 1e-9);
    clock.setBuffering(false);
    advance(100);
    assert.ok(Math.abs(clock.time - 0.2) < 1e-9);
  });

  it('pauses in a hidden tab and resumes when shown, unless exporting', () => {
    const { clock, events, advance } = setup();
    clock.play();
    clock.setHidden(true);
    assert.equal(clock.getState().playing, false);
    assert.deepEqual(events.at(-1), { type: 'pause', reason: 'hidden' });
    clock.setHidden(false);
    assert.equal(clock.getState().playing, true);
    clock.setExporting(true);
    clock.setHidden(true);
    advance(100);
    assert.equal(clock.getState().playing, true);
  });

  it('throttles tick notifications but never seeks', () => {
    const { clock, advance } = setup();
    const seen: number[] = [];
    clock.subscribe((s) => seen.push(s.time), 100);
    clock.play();
    advance(1000, 60);
    assert.ok(seen.length <= 12 && seen.length >= 9, `got ${seen.length}`);
    const before = seen.length;
    clock.seek(5);
    assert.equal(seen.length, before + 1);
  });

  it('keeps the playhead when the edit gets shorter, clamped to the end', () => {
    const { clock } = setup();
    clock.seek(4);
    clock.setDuration(8);
    assert.equal(clock.time, 4);
    clock.setDuration(3);
    assert.equal(clock.time, 3);
  });
});
