import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { completedSentences, parseInline, parseMarkdownLite } from './markdownLite.ts';

describe('markdown-lite', () => {
  it('parses inline marks, links, citations and timecodes', () => {
    assert.deepEqual(parseInline('Cut **two** silences at 1:05 [2], see [docs](https://x.dev) and `trim`.'), [
      { type: 'text', text: 'Cut ' },
      { type: 'strong', text: 'two' },
      { type: 'text', text: ' silences at ' },
      { type: 'timecode', text: '1:05' },
      { type: 'text', text: ' ' },
      { type: 'citation', index: 2 },
      { type: 'text', text: ', see ' },
      { type: 'link', text: 'docs', href: 'https://x.dev' },
      { type: 'text', text: ' and ' },
      { type: 'code', text: 'trim' },
      { type: 'text', text: '.' },
    ]);
  });

  it('never turns unsafe links into links', () => {
    const inlines = parseInline('[x](javascript:alert(1))');
    assert.ok(inlines.every((inline) => inline.type !== 'link'));
  });

  it('parses blocks', () => {
    const blocks = parseMarkdownLite('### Plan\nFirst line\nsame paragraph\n\n- one\n- two\n1. a\n\n```\ncode\n```');
    assert.deepEqual(
      blocks.map((block) => block.type),
      ['heading', 'paragraph', 'list', 'list', 'code'],
    );
    const list = blocks[2];
    assert.ok(list.type === 'list' && list.items.length === 2 && !list.ordered);
  });

  it('keeps only finished sentences', () => {
    assert.equal(completedSentences('Done. Now trim'), 'Done.');
    assert.equal(completedSentences('No stop yet'), '');
  });
});
