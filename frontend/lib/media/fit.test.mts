import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { aspectOf, clearsVertically, combinedSafeZone, containRect, placeSource, SAFE_ZONES, safeRect, unsafeBands } from './fit.ts';

const stage = { width: 270, height: 480 };

describe('frame fit', () => {
  it('names aspects and fits the stage into its box', () => {
    assert.equal(aspectOf({ width: 1080, height: 1920 }), '9:16');
    assert.equal(aspectOf({ width: 1080, height: 1350 }), '4:5');
    assert.equal(aspectOf({ width: 720, height: 720 }), '1:1');
    assert.equal(aspectOf({ width: 1280, height: 720 }), '16:9');
    assert.deepEqual(containRect({ width: 1080, height: 1920 }, { width: 600, height: 480 }), { x: 165, y: 0, width: 270, height: 480 });
  });

  it('fills the frame with a landscape source, centred on (x, y) without leaving gaps', () => {
    const frame = { width: 1080, height: 1920 };
    const source = { width: 1920, height: 1080 };
    const centred = placeSource(source, frame, { x: 0.5, y: 0.5, scale: 1 });
    assert.equal(centred.height, 1);
    assert.ok(Math.abs(centred.x - (0.5 - centred.width / 2)) < 1e-9);
    assert.equal(placeSource(source, frame, { x: 0, y: 0.5, scale: 1 }).x, 0, 'clamped to the left edge');
    const zoomed = placeSource(source, frame, { x: 0.5, y: 0.5, scale: 2 });
    assert.equal(zoomed.height, 2);
    assert.equal(zoomed.y, -0.5);
  });

  it('marks the safe zones on 9:16 only', () => {
    const reels = safeRect(stage, SAFE_ZONES.reels)!;
    assert.ok(Math.abs(reels.y - 0.14 * 480) < 1e-9);
    assert.ok(Math.abs(reels.height - 0.51 * 480) < 1e-9);
    assert.equal(safeRect({ width: 480, height: 270 }, SAFE_ZONES.reels), null);
    assert.equal(unsafeBands({ width: 480, height: 270 }, SAFE_ZONES.reels).length, 0);
    assert.equal(unsafeBands(stage, SAFE_ZONES.shorts).length, 4);
  });

  it('combines platforms by their tightest margins', () => {
    const both = combinedSafeZone();
    assert.equal(both.top, 0.14);
    assert.equal(both.bottom, 0.35);
    assert.equal(both.right, SAFE_ZONES.shorts.right);
    assert.equal(clearsVertically(0.5, both), true);
    assert.equal(clearsVertically(0.7, both), false);
  });
});
