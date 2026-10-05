// Keeps app/tokens.css in step with lib/design/tokens.ts: `npm test`.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import { colors, renderTokensCss } from './tokens.ts';

describe('design tokens', () => {
  it('app/tokens.css is generated from tokens.ts', () => {
    const css = readFileSync(new URL('../../app/tokens.css', import.meta.url), 'utf8');
    assert.equal(css, renderTokensCss(), 'Run `node lib/design/write-tokens-css.mts` to regenerate app/tokens.css');
  });

  it('both themes define the same colour tokens', () => {
    assert.deepEqual(Object.keys(colors.light).sort(), Object.keys(colors.dark).sort());
  });

  it('only declares namespaced variables', () => {
    const names = renderTokensCss().match(/--[\w-]+(?=:)/g) ?? [];
    assert.ok(names.length > 0);
    for (const name of names) assert.match(name, /^--cn-/);
  });
});
