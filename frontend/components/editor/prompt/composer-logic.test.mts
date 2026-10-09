import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import '../../../lib/editor/dev/resolve-hooks.mts';

const logic = await import('./composer-logic.ts');
const { turnFromRun } = await import('../../../lib/editor/run-store.ts');

type Turn = Parameters<typeof logic.liveStep>[0];
const turn = (patch: Partial<Turn>): Turn =>
  ({ ...turnFromRun({ id: 'r1', project_id: 'p', status: 'executing', mode: 'edit', prompt: 'Trim', credits: { estimate: 0, held: 0, spent: 0 }, last_event_seq: 0, created_at: '2026-10-08T00:00:00Z' }), ...patch }) as Turn;

describe('composer logic', () => {
  it('cycles modes with ⇧Tab', () => {
    assert.equal(logic.nextMode('edit'), 'ask');
    assert.equal(logic.nextMode('ask'), 'plan');
    assert.equal(logic.nextMode('plan'), 'edit');
  });

  it('blocks sending for the right reason, in order', () => {
    const ok = { hydrated: true, projectReady: true, online: true, readOnly: false, shortOfCredits: false };
    assert.equal(logic.composerBlock(ok), null);
    assert.deepEqual(logic.composerBlock({ ...ok, hydrated: false }), { disabled: true });
    assert.equal(logic.composerBlock({ ...ok, projectReady: false })?.disabled, true);
    assert.equal(logic.composerBlock({ ...ok, readOnly: true, online: false })?.disabled, true);
    // Offline and short of credits keep the text editable.
    assert.equal(logic.composerBlock({ ...ok, online: false })?.disabled, false);
    assert.match(logic.composerBlock({ ...ok, shortOfCredits: true })?.reason ?? '', /credits/);
  });

  it('estimates only real prompts and flags a short balance', () => {
    assert.equal(logic.wantsEstimate('  '), false);
    assert.equal(logic.wantsEstimate('/cap'), false);
    assert.equal(logic.wantsEstimate('Trim the pauses'), true);
    assert.equal(logic.isShortOfCredits({ credits: 12, free: false, needs_approval: false, balance: 6 }), true);
    assert.equal(logic.isShortOfCredits({ credits: 12, free: true, needs_approval: false, balance: 0 }), false);
    assert.equal(logic.isShortOfCredits({ credits: 12, free: false, needs_approval: false }), false);
    assert.equal(logic.shortOfCreditsText({ credits: 12, free: false, needs_approval: false, balance: 6 }), 'Needs 12 credits; you have 6.');
  });

  it('shows the queue count first, then the estimate', () => {
    const estimate = { credits: 1, free: false, needs_approval: false };
    assert.equal(logic.composerHint(estimate, 2), '2 waiting');
    assert.equal(logic.composerHint(estimate, 0), '≈ 1 credit');
    assert.equal(logic.composerHint({ ...estimate, credits: 12 }, 0), '≈ 12 credits');
    assert.equal(logic.composerHint({ ...estimate, free: true }, 0), 'Free');
    assert.equal(logic.composerHint(undefined, 0), undefined);
  });

  it('words a failed send', () => {
    const describe = (code?: string) => `copy for ${code}`;
    assert.deepEqual(logic.sendIssue({ code: 'NETWORK' }, describe), { kind: 'offline', text: 'Not sent. Check your connection.' });
    assert.equal(logic.sendIssue({ code: 'INSUFFICIENT_CREDITS' }, describe).kind, 'credits');
    assert.deepEqual(logic.sendIssue({ code: 'BOOM' }, describe), { kind: 'other', text: 'Not sent. copy for BOOM' });
  });

  it('turns a queue change into removals, edits and moves', () => {
    const a = { id: 'a', prompt: 'one', chips: [] };
    const b = { id: 'b', prompt: 'two', chips: [] };
    const c = { id: 'c', prompt: 'three', chips: [] };
    assert.deepEqual(logic.diffQueue([a, b, c], [a, c]), { removed: ['b'], edited: [], moved: [] });
    assert.deepEqual(logic.diffQueue([a, b], [{ ...a, prompt: 'uno' }, b]), { removed: [], edited: [{ id: 'a', prompt: 'uno' }], moved: [] });
    assert.deepEqual(logic.diffQueue([a, b, c], [b, a, c]), { removed: [], edited: [], moved: [{ id: 'a', position: 2 }, { id: 'b', position: 1 }] });
    assert.deepEqual(logic.queueItems([turn({ id: 't1', prompt: 'old' })], { t1: 'new' })[0].prompt, 'new');
  });

  it('names the live step for the phone line', () => {
    assert.equal(logic.liveStep(turn({ status: 'sending' })), 'Reading your request');
    assert.equal(logic.liveStep(turn({ status: 'executing', stopping: true })), 'Stopping');
    const steps: Turn['steps'] = [
      { id: '1', label: 'Transcribing', status: 'done' },
      { id: '2', label: 'Trimming silences', status: 'active', progress: '9 of 14' },
      { id: '3', label: 'Captions', status: 'queued' },
    ];
    assert.equal(logic.liveStep(turn({ status: 'executing', steps })), 'Trimming silences · step 2 of 3 · 9 of 14');
    assert.equal(logic.liveStep(turn({ status: 'executing', steps: [] })), 'Working on it');
  });

  it('says "What next?" after a result with nothing selected', () => {
    assert.equal(logic.composerPlaceholder(turn({ status: 'succeeded' }), 0), 'What next?');
    assert.equal(logic.composerPlaceholder(turn({ status: 'succeeded' }), 1), undefined);
    assert.equal(logic.composerPlaceholder(turn({ status: 'failed' }), 0), undefined);
    assert.equal(logic.composerPlaceholder(undefined, 0), undefined);
  });
});
