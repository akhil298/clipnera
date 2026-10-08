import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { expiryFromUrl, MediaUrlError, MediaUrls, type MediaRef } from './urls.ts';

const asset = { id: 'a', kind: 'video' as const, key: 'k/a', proxy: 'p/a', frames: 10, width: 1, height: 1, has_audio: false };
const ref: MediaRef = { kind: 'asset', asset };

function setup(expiresIn = 600_000) {
  let now = 1_000_000;
  let calls = 0;
  const seen: boolean[] = [];
  const urls = new MediaUrls(async (_r, { refresh }) => {
    calls += 1;
    seen.push(refresh);
    return { url: `https://cdn/a?v=${calls}`, expiresAt: now + expiresIn };
  }, { now: () => now, marginMs: 60_000 });
  return { urls, seen, calls: () => calls, tick: (ms: number) => (now += ms) };
}

describe('signed media URLs', () => {
  it('reads the expiry off S3 and CloudFront links', () => {
    assert.equal(expiryFromUrl('https://b.s3.amazonaws.com/k?X-Amz-Date=20261005T120000Z&X-Amz-Expires=3600&X-Amz-Signature=x'),
      Date.UTC(2026, 9, 5, 13, 0, 0));
    assert.equal(expiryFromUrl('https://d.cloudfront.net/k?Expires=1791201600&Signature=x'), 1791201600 * 1000);
    assert.equal(expiryFromUrl('https://cdn/k'), null);
  });

  it('caches, and refreshes ahead of expiry while still serving the old link', async () => {
    const { urls, calls, seen, tick } = setup();
    assert.equal(await urls.get(ref), 'https://cdn/a?v=1');
    assert.equal(await urls.get(ref), 'https://cdn/a?v=1');
    assert.equal(calls(), 1);
    tick(550_000);
    assert.equal(urls.peek(ref), 'https://cdn/a?v=1', 'still valid, refreshing in the background');
    await new Promise((r) => setImmediate(r));
    assert.equal(urls.peek(ref), 'https://cdn/a?v=2');
    assert.deepEqual(seen, [false, true]);
  });

  it('shares one refresh between failures and ignores stale failures', async () => {
    const { urls, calls } = setup();
    const first = await urls.get(ref);
    const [a, b] = await Promise.all([urls.refresh(ref, first), urls.refresh(ref, first)]);
    assert.equal(a, b);
    assert.equal(calls(), 2);
    assert.equal(await urls.refresh(ref, first), a, 'already replaced: no new request');
    assert.equal(calls(), 2);
  });

  it('gives up after repeated failures until a link plays', async () => {
    const { urls } = setup();
    let url = await urls.get(ref);
    url = await urls.refresh(ref, url);
    url = await urls.refresh(ref, url);
    await assert.rejects(urls.refresh(ref, url), MediaUrlError);
    urls.confirm(ref);
    assert.ok(await urls.refresh(ref, url));
  });

  it('wraps resolver failures', async () => {
    const urls = new MediaUrls(async () => { throw new Error('403'); });
    await assert.rejects(urls.get(ref), (e: unknown) => e instanceof MediaUrlError && e.ref === ref);
  });
});
