import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import '../../../lib/editor/dev/resolve-hooks.mts';

const { splitCited, toChipCitation, momentFromFinding, replySources, summariseResult, ordinal, firstTimecodeIn } = await import('./citations.ts');

const c = (id: string, s: number) => ({ id, start_f: s * 30, end_f: (s + 2) * 30, text: `line ${id}` });

describe('citations', () => {
  it('splits prose and chips, dropping unknown ids', () => {
    const parts = splitCited('At 0:12 [[c1]] and [[zz]] there.', [c('c1', 12)]);
    assert.deepEqual(
      parts.map((p) => (p.kind === 'text' ? p.text : p.citations.map((x) => x.id).join())),
      ['At 0:12 ', 'c1', ' and ', ' there.'],
    );
  });

  it('collapses three or more in one sentence, not across sentences', () => {
    const cites = [c('a', 1), c('b', 2), c('d', 3), c('e', 4)];
    const parts = splitCited('One [[a]], [[b]] and [[d]]. Two [[e]].', cites);
    const chips = parts.filter((p) => p.kind === 'cite');
    assert.equal(chips.length, 2);
    assert.equal(chips[0].kind === 'cite' && chips[0].citations.length, 3);
  });

  it('holds back a half-written token while streaming', () => {
    const parts = splitCited('See [[c', [], true);
    assert.deepEqual(parts, [{ kind: 'text', text: 'See ' }]);
  });

  it('converts frames to seconds and unquotes finding labels', () => {
    assert.deepEqual(toChipCitation(c('c1', 12), 30), { start: 12, end: 14, quote: 'line c1', thumbnail: undefined });
    const moment = momentFromFinding({ id: 'f', start_f: 360, end_f: 480, label: '“a coffee”', tag: 'Habit' }, 30);
    assert.equal(moment.quote, 'a coffee');
    assert.equal(moment.duration, 4);
  });

  it('shows a source strip only for findings or 2+ distinct cited moments', () => {
    assert.equal(replySources([], [c('a', 1)]).length, 0);
    assert.equal(replySources([], [c('a', 1), { ...c('b', 1) }]).length, 0);
    assert.equal(replySources([], [c('a', 1), c('b', 5)]).length, 2);
  });

  it('counts the result', () => {
    const base = { status: 'partial' as const, version: null, suggestions: [], credits: { estimate: 1, held: 0, spent: 1 }, duration_ms: 0 };
    assert.equal(summariseResult({ ...base, summary: { done: ['A'], not_done: [{ text: 'B', reason: 'r' }] } }, false).summary, '1 of 2 done.');
    assert.equal(summariseResult({ ...base, summary: { done: [], not_done: [{ text: 'B', reason: 'only 18 seconds' }] } }, false).summary, 'Nothing changed: only 18 seconds.');
    assert.equal(summariseResult({ ...base, summary: { done: ['A'], not_done: [{ text: 'B', reason: 'r' }] } }, true).summary, 'Stopped · 1 of 2 done.');
  });

  it('formats ordinals and finds timecodes', () => {
    assert.deepEqual([1, 2, 3, 4, 11, 22].map(ordinal), ['1st', '2nd', '3rd', '4th', '11th', '22nd']);
    assert.equal(firstTimecodeIn('around 1:05 or so'), '1:05');
    assert.equal(firstTimecodeIn('no time'), null);
  });
});
