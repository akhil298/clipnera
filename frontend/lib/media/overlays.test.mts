import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import './testing/resolve-ts.mts';
import { timeline } from './testing/fixtures.mts';

const { audibleAt, captionAt, cuesBetween, dbToGain, DUCK_DB, evaluateOverlays, groupCaptionWords, itemAfter, itemAt, keyframeValue } =
  await import('./overlays.ts');

const near = (a: number, b: number) => assert.ok(Math.abs(a - b) < 1e-9, `${a} ≉ ${b}`);
const words = [
  { text: 'Hey', start: 0, end: 0.3 }, { text: 'there.', start: 0.3, end: 0.6 },
  { text: 'This', start: 1.0, end: 1.2 }, { text: 'is', start: 1.2, end: 1.4 },
  { text: 'great', start: 1.4, end: 1.6 }, { text: 'stuff', start: 1.6, end: 1.8 },
];

describe('overlay evaluation', () => {
  it('finds the picture, its source time and keyframed transform', () => {
    const o = evaluateOverlays(timeline, 0.5);
    assert.equal(o.frame, 15);
    assert.equal(o.base?.item.id, 'c1');
    near(o.base!.sourceTime, 1.5);
    near(o.base!.transform.scale, 1.125);
    assert.equal(o.base!.opacity, 1);
    assert.deepEqual(o.broll, []);
    assert.equal(o.hook?.item.text, 'Watch this');
    near(o.hook!.progress, 0.25);
  });

  it('layers B-roll over the picture', () => {
    const o = evaluateOverlays(timeline, 1.5);
    assert.deepEqual(o.layers.map((l) => l.item.id), ['c1', 'br']);
    assert.equal(o.broll[0].asset.kind, 'image');
    assert.equal(o.broll[0].sourceTime, 0);
  });

  it('runs the way in, at clip speed, and turns slides into fades for reduced motion', () => {
    const o = evaluateOverlays(timeline, 3.1);
    assert.equal(o.base?.item.id, 'c2');
    near(o.base!.sourceTime, 0.2);
    assert.equal(o.base!.transition?.type, 'slide_left');
    near(o.base!.transition!.progress, 0.3);
    assert.equal(o.hook, null);
    assert.equal(evaluateOverlays(timeline, 3.1, { reducedMotion: true }).base!.transition?.type, 'fade');
    assert.equal(evaluateOverlays(timeline, 3.5).base!.transition, null);
  });

  it('shows nothing past the end', () => {
    const o = evaluateOverlays(timeline, 5);
    assert.deepEqual([o.base, o.layers.length, o.texts.length], [null, 0, 0]);
  });

  it('builds caption lines like the burner and lights the spoken word', () => {
    assert.deepEqual(groupCaptionWords(words).map((l) => l.map((w) => w.text)), [['Hey', 'there.'], ['This', 'is', 'great'], ['stuff']]);
    assert.equal(captionAt(words, 0.65)?.activeIndex, 1, 'a word lingers briefly after it ends');
    assert.equal(captionAt(words, 0.9), null, 'nothing between lines');
    assert.equal(captionAt(words, 1.25)?.activeIndex, 1);
    const o = evaluateOverlays(timeline, 1.25, { words });
    assert.equal(o.caption?.style, 'karaoke');
    assert.equal(o.caption?.words[o.caption.activeIndex].text, 'is');
    const off = { ...timeline, captions: { ...timeline.captions!, enabled: false } };
    assert.equal(evaluateOverlays(off, 1.25, { words }).caption, null);
  });

  it('eases keyframes and holds them past either end', () => {
    const pts = [{ f: 10, v: 0, ease: 'in' as const }, { f: 20, v: 1, ease: 'linear' as const }];
    assert.equal(keyframeValue(pts, 0, 9), 0);
    assert.equal(keyframeValue(pts, 15, 9), 0.25);
    assert.equal(keyframeValue(pts, 99, 9), 1);
    assert.equal(keyframeValue(undefined, 5, 9), 9);
  });

  it('looks items up by frame', () => {
    const items = timeline.tracks[0].items;
    assert.equal(itemAt(items, 89)?.id, 'c1');
    assert.equal(itemAt(items, 90)?.id, 'c2');
    assert.equal(itemAt(items, 150), null);
    assert.equal(itemAfter(items, 10)?.id, 'c2');
  });

  it('fires each sound effect once as playback passes it', () => {
    assert.deepEqual(cuesBetween(timeline, 1.4, 1.5).map((s) => s.id), ['fx0']);
    assert.deepEqual(cuesBetween(timeline, 1.5, 1.6), []);
    assert.deepEqual(cuesBetween(timeline, 1.5, 1.4), []);
  });

  it('plays the audio tracks, ducking music under speech', () => {
    const a = audibleAt(timeline, 1);
    assert.deepEqual(a.map((x) => x.item.id), ['vo1', 'm0']);
    near(a[0].sourceTime, 1);
    assert.equal(a[0].gain, 0.8);
    near(a[1].sourceTime, 3);
    near(a[1].gain, dbToGain(-20 + DUCK_DB));
    const quiet = { ...timeline, tracks: timeline.tracks.map((t) => (t.id === 'voice' ? { ...t, muted: true } : t)) };
    near(audibleAt(quiet, 1)[0].gain, dbToGain(-20));
  });
});
