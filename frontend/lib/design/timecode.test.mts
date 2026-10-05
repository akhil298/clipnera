import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { formatTimecode, isoDuration, parseTimecode, spokenDuration } from './timecode.ts';

describe('timecode', () => {
  it('formats minutes, hours and frames', () => {
    assert.equal(formatTimecode(0), '0:00');
    assert.equal(formatTimecode(65), '1:05');
    assert.equal(formatTimecode(3725), '1:02:05');
    assert.equal(formatTimecode(65, { hours: true }), '0:01:05');
    assert.equal(formatTimecode(65, { total: 700 }), '01:05');
    assert.equal(formatTimecode(65, { total: 4000 }), '0:01:05');
    assert.equal(formatTimecode(65.5, { fps: 30 }), '1:05:15');
    assert.equal(formatTimecode(-3), '0:00');
    assert.equal(formatTimecode(Number.NaN), '0:00');
  });

  it('parses only real timecodes', () => {
    assert.equal(parseTimecode('1:05'), 65);
    assert.equal(parseTimecode('01:02:05'), 3725);
    assert.equal(parseTimecode('1:75'), null);
    assert.equal(parseTimecode('12'), null);
    assert.equal(parseTimecode('1:5'), null);
  });

  it('speaks and serialises durations', () => {
    assert.equal(spokenDuration(65), '1 minute 5 seconds');
    assert.equal(spokenDuration(3600), '1 hour');
    assert.equal(spokenDuration(0), '0 seconds');
    assert.equal(isoDuration(65.5), 'PT65.5S');
  });
});
