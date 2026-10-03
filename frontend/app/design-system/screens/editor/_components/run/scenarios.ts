/**
 * Scripted runs for the mockups. Each beat waits `after` ms (scaled by the
 * replay speed) and then emits one event; gates wait for the person. Timings
 * of the "happy" run follow the storyboard in
 * docs/revamp/screens/02-editor-and-export.md §3, against the 01 §5 budgets.
 */

import type { PromptContext } from '@/components/ui/ContextChip';
import type { PromptMode } from '@/components/ui/PromptBar';

import { CAPTION_IDS, CHIP_CLIP, CHIP_RANGE } from '../sample';
import type { Credits, RunEvent } from './events';

export type Beat = { after: number; event: RunEvent } | { gate: 'answer' } | { gate: 'decision' };

export interface Scenario {
  id: string;
  label: string;
  /** What this scenario shows, for the switcher. */
  note: string;
  prompt: string;
  mode: PromptMode;
  chips: PromptContext[];
  baseRevision: number;
  beats: Beat[];
  /** Played when the person picks "Finish with what's done" (or "Not now" on an approval). */
  finish?: Beat[];
  /** Mock-only extension: the B-roll pick shown under the result (05-broll §8.3). */
  pick?: { title: string; source: string; range: string; reasons: string[] };
}

const credits = (estimate: number, spent = 0): Credits => ({ estimate, held: estimate, spent });

/** Streams a sentence as word groups about every 80 ms (events.md: run.plan.delta is coalesced ~80 ms). */
function stream(text: string, type: 'run.plan.delta' | 'run.message.delta', first = 80): Beat[] {
  const words = text.split(' ');
  const beats: Beat[] = [];
  for (let index = 0; index < words.length; index += 3) {
    const chunk = `${words.slice(index, index + 3).join(' ')} `;
    const event: RunEvent =
      type === 'run.plan.delta' ? { type, data: { text: chunk } } : { type, data: { text: chunk, role: 'answer' } };
    beats.push({ after: index === 0 ? first : 80, event });
  }
  return beats;
}

const ack = (mode: PromptMode, chips: PromptContext[], base: number, estimate: number): Beat => ({
  after: 120,
  event: { type: 'run.acknowledged', data: { mode, chips, base_revision: base, credits: credits(estimate) } },
});

const started = (after: number, step_id: string, index: number, total: number, label: string): Beat => ({
  after,
  event: { type: 'run.step.started', data: { step_id, index, total, label } },
});

const progress = (after: number, step_id: string, value: { done?: number; total?: number; percent?: number; label?: string }): Beat => ({
  after,
  event: { type: 'run.step.progress', data: { step_id, ...value } },
});

const completed = (after: number, step_id: string, label: string, summary: string, revisions: number[] = []): Beat => ({
  after,
  event: { type: 'run.step.completed', data: { step_id, label, summary, revisions } },
});

const applied = (after: number, revision: number, item_ids: string[], range: [number, number], step_id: string): Beat => ({
  after,
  event: {
    type: 'run.operation.applied',
    data: { revision, base_revision: revision - 1, changed_ranges: [range], item_ids, step_id },
  },
});

const lock = (after: number, type: 'run.lock.acquired' | 'run.lock.released', step_id: string, item_ids: string[]): Beat => ({
  after,
  event: { type, data: { step_id, item_ids } },
});

const check = (after: number, passed = true, findings: { severity: 'info' | 'warn'; text: string }[] = []): Beat[] => [
  { after, event: { type: 'run.check.started', data: {} } },
  { after: 2300, event: { type: 'run.check.completed', data: { passed, findings } } },
];

const finishedVersion = (name: string, revision: number, balance: number): Beat[] => [
  { after: 60, event: { type: 'version.created', data: { version_id: `v_${revision}`, name } } },
  { after: 60, event: { type: 'credits.updated', data: { balance } } },
];

const PLAN_TRIM = 'I’ll find the pauses longer than half a second across this clip, cut them, then add captions in your brand style.';

const TRIM_PLAN: Beat = {
  after: 120,
  event: {
    type: 'run.plan',
    data: {
      sentences: [PLAN_TRIM],
      steps: [
        { id: 's1', label: 'Finding silences' },
        { id: 's2', label: 'Trimming silences' },
        { id: 's3', label: 'Adding captions' },
      ],
      credits: credits(4),
      needs_approval: false,
    },
  },
};

/** Steps 1–2 of the trim run: shared by several scenarios. */
const TRIM_FIRST_HALF: Beat[] = [
  ack('edit', [CHIP_CLIP], 40, 4),
  ...stream(PLAN_TRIM, 'run.plan.delta', 780),
  TRIM_PLAN,
  started(100, 's1', 1, 3, 'Finding silences'),
  progress(2400, 's1', { percent: 60, label: '43 of 72 s listened' }),
  completed(1800, 's1', 'Finding silences', 'Found 14 silences'),
  started(60, 's2', 2, 3, 'Trimming 14 silences'),
  lock(40, 'run.lock.acquired', 's2', ['v2', 'v3']),
  progress(800, 's2', { done: 6, total: 14 }),
  applied(1400, 41, ['v1', 'v2', 'v3'], [0, 30], 's2'),
  lock(100, 'run.lock.released', 's2', ['v2', 'v3']),
  completed(60, 's2', 'Trimming 14 silences', 'Removed 42 seconds', [41]),
];

const CAPTION_STEPS: Beat[] = [
  started(100, 's3', 3, 3, 'Adding captions'),
  lock(40, 'run.lock.acquired', 's3', CAPTION_IDS.slice(0, 1).concat(['v1'])),
  progress(1600, 's3', { done: 4, total: 9 }),
  applied(1600, 42, CAPTION_IDS, [0, 30], 's3'),
  lock(100, 'run.lock.released', 's3', CAPTION_IDS.slice(0, 1).concat(['v1'])),
  completed(60, 's3', 'Adding captions', 'Added 9 caption lines in Bold pop', [42]),
];

const TRIM_SUGGESTIONS = [
  { label: 'Make the hook punchier', prompt: 'Make the opening hook punchier' },
  { label: 'Add B-roll at 0:12', prompt: 'Add B-roll of coffee being poured over 0:12 – 0:16' },
  { label: 'Export for Reels', prompt: 'Export for Instagram Reels at 1080p' },
];

const TRIM_RESULT: Beat = {
  after: 200,
  event: {
    type: 'run.result',
    data: {
      status: 'succeeded',
      version: { id: 'v_42', name: 'Trimmed silences, added captions', result_revision: 42 },
      summary: { done: ['Removed 14 silences (42 seconds); the clip is now 0:30', 'Added 9 caption lines in Bold pop'], not_done: [] },
      suggestions: TRIM_SUGGESTIONS,
      credits: credits(4, 4),
      duration_ms: 15200,
    },
  },
};

export const SCENARIOS: ReadonlyArray<Scenario> = [
  {
    id: 'happy',
    label: 'Trim and caption',
    note: 'The storyboard run: plan, 3 steps, 2 timeline updates, check, result, full quality.',
    prompt: 'remove the silences and add captions',
    mode: 'edit',
    chips: [CHIP_CLIP],
    baseRevision: 40,
    beats: [
      ...TRIM_FIRST_HALF,
      ...CAPTION_STEPS,
      ...check(100),
      TRIM_RESULT,
      ...finishedVersion('Trimmed silences, added captions', 42, 1236),
      { after: 5200, event: { type: 'job.succeeded', data: { kind: 'run.render_full' } } },
    ],
  },
  {
    id: 'question',
    label: 'Asks a question',
    note: 'A choice card mid-run; the run carries on after the pick. Ends with the B-roll “why” line and Swap.',
    prompt: 'add B-roll where I talk about coffee',
    mode: 'edit',
    chips: [CHIP_CLIP],
    baseRevision: 42,
    pick: {
      title: 'Pouring coffee into a white mug',
      source: 'your uploads',
      range: '0:12 – 0:16',
      reasons: ['matches “coffee” and “pour”', 'from your library', 'fits 9:16'],
    },
    beats: [
      ack('edit', [CHIP_CLIP], 42, 2),
      ...stream('I’ll find where you talk about coffee and place a matching shot over it, from your uploads first.', 'run.plan.delta', 700),
      {
        after: 120,
        event: {
          type: 'run.plan',
          data: {
            sentences: ['I’ll find where you talk about coffee and place a matching shot over it, from your uploads first.'],
            steps: [
              { id: 's1', label: 'Finding the moment' },
              { id: 's2', label: 'Choosing a shot' },
              { id: 's3', label: 'Placing B-roll' },
            ],
            credits: credits(2),
            needs_approval: false,
          },
        },
      },
      started(100, 's1', 1, 3, 'Finding the moment'),
      {
        after: 1600,
        event: {
          type: 'run.question',
          data: {
            question_id: 'q1',
            text: 'You mention coffee twice. Which one should get B-roll?',
            choices: [
              { id: 'a', label: '0:12 — “less than two coffees”', hint: 'The price comparison' },
              { id: 'b', label: '0:24 — “a coffee a day”', hint: 'The habit line' },
              { id: 'c', label: 'Both', hint: 'Two shots, 4 s each' },
            ],
            allow_skip: true,
          },
        },
      },
      { gate: 'answer' },
      completed(300, 's1', 'Finding the moment', 'Using 0:12 – 0:16'),
      started(60, 's2', 2, 3, 'Choosing a shot'),
      progress(900, 's2', { label: 'Searching both libraries' }),
      completed(1500, 's2', 'Choosing a shot', 'Chose “Pouring coffee” from your uploads'),
      started(60, 's3', 3, 3, 'Placing B-roll'),
      lock(40, 'run.lock.acquired', 's3', ['v2']),
      applied(1200, 43, ['b1'], [12, 16], 's3'),
      lock(100, 'run.lock.released', 's3', ['v2']),
      completed(60, 's3', 'Placing B-roll', 'Added a 4-second shot at 0:12', [43]),
      ...check(100),
      {
        after: 200,
        event: {
          type: 'run.result',
          data: {
            status: 'succeeded',
            version: { id: 'v_43', name: 'Added B-roll at 0:12', result_revision: 43 },
            summary: { done: ['Added B-roll at 0:12 – 0:16'], not_done: [] },
            suggestions: [
              { label: 'Add B-roll at 0:24 too', prompt: 'Add B-roll over 0:24 – 0:28' },
              { label: 'Make it 3 seconds', prompt: 'Shorten the B-roll at 0:12 to 3 seconds' },
            ],
            credits: credits(2, 2),
            duration_ms: 9800,
          },
        },
      },
      ...finishedVersion('Added B-roll at 0:12', 43, 1234),
    ],
  },
  {
    id: 'approval',
    label: 'Approval pause',
    note: 'Removes over half the clip, so it pauses on “Go ahead” before changing anything (01 §5).',
    prompt: 'cut this down to the best 15 seconds',
    mode: 'edit',
    chips: [CHIP_CLIP],
    baseRevision: 40,
    beats: [
      ack('edit', [CHIP_CLIP], 40, 6),
      ...stream('I’ll keep your three strongest lines and remove the rest: about 57 seconds of the 1:12.', 'run.plan.delta', 760),
      {
        after: 120,
        event: {
          type: 'run.plan',
          data: {
            sentences: ['I’ll keep your three strongest lines and remove the rest: about 57 seconds of the 1:12.'],
            steps: [
              { id: 's1', label: 'Ranking your lines' },
              { id: 's2', label: 'Removing 57 seconds' },
            ],
            credits: credits(6),
            needs_approval: true,
          },
        },
      },
      {
        after: 200,
        event: {
          type: 'run.paused',
          data: {
            reason: 'approval',
            credits: credits(6),
            approval: { kind: 'removal', text: 'This removes 79% of the clip.', share_removed: 0.79 },
            options: ['continue', 'finish'],
          },
        },
      },
      { gate: 'decision' },
      { after: 150, event: { type: 'run.resumed', data: { reason: 'user_continue' } } },
      started(80, 's1', 1, 2, 'Ranking your lines'),
      progress(1500, 's1', { done: 11, total: 23 }),
      completed(1500, 's1', 'Ranking your lines', 'Kept 3 of 23 lines'),
      started(60, 's2', 2, 2, 'Removing 57 seconds'),
      applied(1600, 41, ['v1', 'v2', 'v3'], [0, 30], 's2'),
      completed(80, 's2', 'Removing 57 seconds', 'The clip is now 0:15', [41]),
      ...check(100),
      {
        after: 200,
        event: {
          type: 'run.result',
          data: {
            status: 'succeeded',
            version: { id: 'v_41', name: 'Cut to the best 15 seconds', result_revision: 41 },
            summary: { done: ['Kept 3 lines; the clip is now 0:15'], not_done: [] },
            suggestions: [{ label: 'Add captions', prompt: 'Add captions in my brand style' }],
            credits: credits(6, 5),
            duration_ms: 8000,
          },
        },
      },
      ...finishedVersion('Cut to the best 15 seconds', 41, 1235),
    ],
    finish: [{ after: 300, event: { type: 'run.cancelled', data: { by: 'user', while: 'running' } } }],
  },
  {
    id: 'credits',
    label: 'Out of credits',
    note: 'Pauses, does not fail. Add credits and resume, or finish with what is done.',
    prompt: 'remove the silences and add captions',
    mode: 'edit',
    chips: [CHIP_CLIP],
    baseRevision: 40,
    beats: [
      ...TRIM_FIRST_HALF,
      {
        after: 200,
        event: {
          type: 'run.paused',
          data: { reason: 'credits', credits: credits(4, 4), needed: 3, options: ['add_credits', 'finish'] },
        },
      },
      { gate: 'decision' },
      { after: 200, event: { type: 'credits.updated', data: { balance: 100 } } },
      { after: 200, event: { type: 'run.resumed', data: { reason: 'credits_added' } } },
      ...CAPTION_STEPS,
      ...check(100),
      TRIM_RESULT,
      ...finishedVersion('Trimmed silences, added captions', 42, 97),
    ],
    finish: [
      ...check(200),
      {
        after: 200,
        event: {
          type: 'run.result',
          data: {
            status: 'partial',
            version: { id: 'v_41', name: 'Trimmed silences', result_revision: 41 },
            summary: {
              done: ['Removed 14 silences (42 seconds)'],
              not_done: [{ text: 'Add captions', reason: 'paused for credits' }],
            },
            suggestions: [{ label: 'Try the rest', prompt: 'Add captions in my brand style' }],
            credits: credits(4, 4),
            duration_ms: 9000,
          },
        },
      },
      ...finishedVersion('Trimmed silences', 41, 0),
    ],
  },
  {
    id: 'step-failed',
    label: 'A step fails',
    note: 'One automatic retry, then the step turns failed. Completed steps stay as a version, with Try again and Undo.',
    prompt: 'remove the silences and add captions',
    mode: 'edit',
    chips: [CHIP_CLIP],
    baseRevision: 40,
    beats: [
      ...TRIM_FIRST_HALF,
      started(100, 's3', 3, 3, 'Adding captions'),
      {
        after: 1800,
        event: {
          type: 'run.step.failed',
          data: {
            step_id: 's3',
            error: { code: 'CAPTION_ALIGN_FAILED', message: 'The captions didn’t line up with the speech.', retryable: true },
            will_retry: true,
            attempt: 1,
          },
        },
      },
      started(600, 's3', 3, 3, 'Adding captions'),
      {
        after: 1800,
        event: {
          type: 'run.step.failed',
          data: {
            step_id: 's3',
            error: { code: 'CAPTION_ALIGN_FAILED', message: 'The captions didn’t line up with the speech.', retryable: true },
            will_retry: false,
            attempt: 2,
          },
        },
      },
      {
        after: 200,
        event: {
          type: 'run.failed',
          data: {
            error: { code: 'CAPTION_ALIGN_FAILED', message: 'I couldn’t add captions: they didn’t line up with the speech.', retryable: true },
            version: { id: 'v_41', name: 'Trimmed silences' },
            credits: credits(4, 2),
          },
        },
      },
      ...finishedVersion('Trimmed silences', 41, 1238),
    ],
  },
  {
    id: 'second-failure',
    label: 'Second failure',
    note: 'No automatic third try: a different prompt to try, and a contact link.',
    prompt: 'add captions',
    mode: 'edit',
    chips: [CHIP_CLIP],
    baseRevision: 41,
    beats: [
      ack('edit', [CHIP_CLIP], 41, 2),
      ...stream('I’ll add captions in your brand style.', 'run.plan.delta', 700),
      {
        after: 120,
        event: {
          type: 'run.plan',
          data: { sentences: ['I’ll add captions in your brand style.'], steps: [{ id: 's1', label: 'Adding captions' }], credits: credits(2), needs_approval: false },
        },
      },
      started(100, 's1', 1, 1, 'Adding captions'),
      {
        after: 1900,
        event: {
          type: 'run.step.failed',
          data: {
            step_id: 's1',
            error: { code: 'CAPTION_ALIGN_FAILED', message: 'The captions didn’t line up with the speech.', retryable: false },
            will_retry: false,
            attempt: 1,
          },
        },
      },
      {
        after: 200,
        event: {
          type: 'run.failed',
          data: {
            error: { code: 'SECOND_FAILURE', message: 'That didn’t work twice.', retryable: false },
            version: null,
            suggestion: { label: 'Use the Plain caption style', prompt: 'Add captions in the Plain style, one line at a time' },
            credits: credits(2, 0),
          },
        },
      },
    ],
  },
  {
    id: 'partial',
    label: 'Partly done',
    note: 'The check finds something it could not fix; the result says so and offers “Try the rest”.',
    prompt: 'add B-roll at 0:12 and keep the captions readable',
    mode: 'edit',
    chips: [CHIP_RANGE],
    baseRevision: 42,
    beats: [
      ack('edit', [CHIP_RANGE], 42, 2),
      ...stream('I’ll place a coffee shot over 0:12 – 0:16 and make sure the captions stay clear of it.', 'run.plan.delta', 700),
      {
        after: 120,
        event: {
          type: 'run.plan',
          data: {
            sentences: ['I’ll place a coffee shot over 0:12 – 0:16 and make sure the captions stay clear of it.'],
            steps: [
              { id: 's1', label: 'Choosing a shot' },
              { id: 's2', label: 'Placing B-roll' },
            ],
            credits: credits(2),
            needs_approval: false,
          },
        },
      },
      started(100, 's1', 1, 2, 'Choosing a shot'),
      completed(1800, 's1', 'Choosing a shot', 'Chose “Pouring coffee”'),
      started(60, 's2', 2, 2, 'Placing B-roll'),
      applied(1300, 43, ['b1'], [12, 16], 's2'),
      completed(80, 's2', 'Placing B-roll', 'Added a 4-second shot at 0:12', [43]),
      ...check(100, false, [{ severity: 'warn', text: 'Captions at 0:12 – 0:16 sit on the bright part of the shot.' }]),
      {
        after: 200,
        event: {
          type: 'run.result',
          data: {
            status: 'partial',
            version: { id: 'v_43', name: 'Added B-roll at 0:12', result_revision: 43 },
            summary: {
              done: ['Added B-roll at 0:12 – 0:16'],
              not_done: [{ text: 'Readable captions at 0:12 – 0:16', reason: 'they sit on the bright part of the shot' }],
            },
            suggestions: [{ label: 'Try the rest', prompt: 'Add a dark box behind the captions at 0:12 – 0:16' }],
            credits: credits(2, 2),
            duration_ms: 7600,
          },
        },
      },
      ...finishedVersion('Added B-roll at 0:12', 43, 1234),
    ],
  },
  {
    id: 'not-enough',
    label: 'Not enough material',
    note: 'Nothing changes; it says what it found and offers alternatives.',
    prompt: 'make a 60-second highlight of the product demo',
    mode: 'edit',
    chips: [],
    baseRevision: 42,
    beats: [
      ack('edit', [], 42, 6),
      ...stream('I’ll find the product demo in the source video and build a 60-second highlight from it.', 'run.plan.delta', 700),
      {
        after: 120,
        event: {
          type: 'run.plan',
          data: {
            sentences: ['I’ll find the product demo in the source video and build a 60-second highlight from it.'],
            steps: [
              { id: 's1', label: 'Finding the product demo' },
              { id: 's2', label: 'Building the highlight' },
            ],
            credits: credits(6),
            needs_approval: false,
          },
        },
      },
      started(100, 's1', 1, 2, 'Finding the product demo'),
      progress(1800, 's1', { done: 7, total: 12, label: '7 of 12:40 searched' }),
      completed(1800, 's1', 'Finding the product demo', 'Found 18 seconds'),
      {
        after: 300,
        event: {
          type: 'run.result',
          data: {
            status: 'partial',
            version: null,
            summary: {
              done: [],
              not_done: [{ text: 'A 60-second highlight', reason: 'there are only 18 seconds of the product demo' }],
            },
            suggestions: [
              { label: 'Make an 18-second demo clip', prompt: 'Make an 18-second clip of the product demo' },
              { label: 'Mix demo and pricing talk', prompt: 'Make a 60-second clip mixing the product demo with the pricing talk' },
            ],
            credits: credits(6, 1),
            duration_ms: 4200,
          },
        },
      },
    ],
  },
  {
    id: 'not-understood',
    label: 'Not understood',
    note: '“I’m not sure which clip you mean.” A choice card with clip previews.',
    prompt: 'make that one punchier',
    mode: 'edit',
    chips: [],
    baseRevision: 42,
    beats: [
      ack('edit', [], 42, 2),
      {
        after: 1100,
        event: {
          type: 'run.question',
          data: {
            question_id: 'q1',
            text: 'I’m not sure which clip you mean.',
            choices: [
              { id: 'c1', label: 'The ₹999 mistake', hint: '0:44 · score 94' },
              { id: 'c2', label: 'Cheaper than two coffees', hint: '0:29 · score 91' },
              { id: 'c3', label: 'Why ₹499 works', hint: '1:12 · open now' },
            ],
            allow_skip: true,
          },
        },
      },
      { gate: 'answer' },
      ...stream('I’ll rewrite the opening hook so the first line lands in under two seconds.', 'run.plan.delta', 300),
      {
        after: 120,
        event: {
          type: 'run.plan',
          data: {
            sentences: ['I’ll rewrite the opening hook so the first line lands in under two seconds.'],
            steps: [{ id: 's1', label: 'Rewriting the hook' }],
            credits: credits(2),
            needs_approval: false,
          },
        },
      },
      started(100, 's1', 1, 1, 'Rewriting the hook'),
      applied(2000, 43, ['t1'], [0, 5], 's1'),
      completed(80, 's1', 'Rewriting the hook', 'New title: “₹499 beat ₹999. Here’s why.”', [43]),
      ...check(100),
      {
        after: 200,
        event: {
          type: 'run.result',
          data: {
            status: 'succeeded',
            version: { id: 'v_43', name: 'Punchier hook', result_revision: 43 },
            summary: { done: ['New title: “₹499 beat ₹999. Here’s why.”'], not_done: [] },
            suggestions: [{ label: 'Try another hook', prompt: 'Give me two other hook options' }],
            credits: credits(2, 1),
            duration_ms: 6100,
          },
        },
      },
      ...finishedVersion('Punchier hook', 43, 1235),
    ],
  },
  {
    id: 'unreadable',
    label: 'File can’t be read',
    note: 'Names the file and what to convert it to; one action: Replace file.',
    prompt: 'clean up the audio',
    mode: 'edit',
    chips: [CHIP_CLIP],
    baseRevision: 42,
    beats: [
      ack('edit', [CHIP_CLIP], 42, 2),
      ...stream('I’ll reduce the room noise and level your voice.', 'run.plan.delta', 700),
      {
        after: 120,
        event: {
          type: 'run.plan',
          data: { sentences: ['I’ll reduce the room noise and level your voice.'], steps: [{ id: 's1', label: 'Reading the audio' }, { id: 's2', label: 'Cleaning up the audio' }], credits: credits(2), needs_approval: false },
        },
      },
      started(100, 's1', 1, 2, 'Reading the audio'),
      {
        after: 1600,
        event: {
          type: 'run.step.failed',
          data: {
            step_id: 's1',
            error: { code: 'MEDIA_UNREADABLE', message: 'I couldn’t read the audio in kavya-interview.mov.', retryable: false },
            will_retry: false,
            attempt: 1,
          },
        },
      },
      {
        after: 200,
        event: {
          type: 'run.failed',
          data: {
            error: { code: 'MEDIA_UNREADABLE', message: 'I couldn’t read the audio in kavya-interview.mov.', retryable: false },
            version: null,
            credits: credits(2, 0),
          },
        },
      },
    ],
  },
  {
    id: 'connection',
    label: 'Connection drops',
    note: '“Reconnecting — your edit is still running.” Missed events replay from a snapshot (sync.reset).',
    prompt: 'remove the silences and add captions',
    mode: 'edit',
    chips: [CHIP_CLIP],
    baseRevision: 40,
    beats: [
      ...TRIM_FIRST_HALF.slice(0, -6),
      { after: 300, event: { type: 'client.connection', data: { online: false } } },
      ...TRIM_FIRST_HALF.slice(-6),
      { after: 1200, event: { type: 'client.connection', data: { online: true } } },
      { after: 200, event: { type: 'sync.reset', data: { reason: 'buffer_miss' } } },
      ...CAPTION_STEPS,
      ...check(100),
      TRIM_RESULT,
      ...finishedVersion('Trimmed silences, added captions', 42, 1236),
    ],
  },
  {
    id: 'ask',
    label: 'Ask mode',
    note: 'Answers without changing anything. Free within a daily allowance (pending owner confirmation).',
    prompt: 'where do I talk about coffee?',
    mode: 'ask',
    chips: [],
    baseRevision: 42,
    beats: [
      ack('ask', [], 42, 0),
      ...stream('You mention coffee twice: at 0:12 (“less than two coffees”) and at 0:24 (“a coffee a day”). The first is the stronger line for B-roll.', 'run.message.delta', 650),
      {
        after: 200,
        event: {
          type: 'run.result',
          data: {
            status: 'succeeded',
            version: null,
            summary: { done: [], not_done: [] },
            answer: 'You mention coffee twice: at 0:12 (“less than two coffees”) and at 0:24 (“a coffee a day”). The first is the stronger line for B-roll.',
            suggestions: [{ label: 'Add B-roll at 0:12', prompt: 'Add B-roll of coffee being poured over 0:12 – 0:16' }],
            credits: credits(0),
            duration_ms: 2400,
          },
        },
      },
    ],
  },
  {
    id: 'plan',
    label: 'Plan mode',
    note: 'Writes a plan to edit and approve. Nothing changes until approval.',
    prompt: 'turn this into a 30-second teaser for Instagram',
    mode: 'plan',
    chips: [CHIP_CLIP],
    baseRevision: 40,
    beats: [
      ack('plan', [CHIP_CLIP], 40, 0),
      ...stream('Here’s how I’d make a 30-second teaser. Change anything, then approve.', 'run.plan.delta', 700),
      {
        after: 120,
        event: {
          type: 'run.plan',
          data: {
            sentences: ['Here’s how I’d make a 30-second teaser. Change anything, then approve.'],
            steps: [
              { id: 's1', label: 'Open on “We tried ₹999 and nobody converted”' },
              { id: 's2', label: 'Remove silences and retakes' },
              { id: 's3', label: 'Add captions in Bold pop' },
              { id: 's4', label: 'Reframe to 9:16 and end on the price' },
            ],
            credits: credits(6),
            needs_approval: false,
          },
        },
      },
      {
        after: 200,
        event: {
          type: 'run.result',
          data: {
            status: 'succeeded',
            version: null,
            summary: { done: [], not_done: [] },
            plan_document: {
              sentences: ['Here’s how I’d make a 30-second teaser. Change anything, then approve.'],
              steps: [
                { id: 's1', label: 'Open on “We tried ₹999 and nobody converted”' },
                { id: 's2', label: 'Remove silences and retakes' },
                { id: 's3', label: 'Add captions in Bold pop' },
                { id: 's4', label: 'Reframe to 9:16 and end on the price' },
              ],
            },
            suggestions: [],
            credits: credits(6),
            duration_ms: 2600,
          },
        },
      },
    ],
  },
];

/** A queued follow-up runs this short script when its turn comes. */
export function followUpBeats(base: number): Beat[] {
  return [
    ack('edit', [], base, 1),
    ...stream('I’ll make the captions 20% bigger and keep them inside the safe area.', 'run.plan.delta', 600),
    {
      after: 120,
      event: {
        type: 'run.plan',
        data: { sentences: ['I’ll make the captions 20% bigger and keep them inside the safe area.'], steps: [{ id: 's1', label: 'Resizing 9 caption lines' }], credits: credits(1), needs_approval: false },
      },
    },
    started(100, 's1', 1, 1, 'Resizing 9 caption lines'),
    applied(1500, base + 1, CAPTION_IDS, [0, 30], 's1'),
    completed(80, 's1', 'Resizing 9 caption lines', 'Captions are now 20% bigger', [base + 1]),
    ...check(100),
    {
      after: 200,
      event: {
        type: 'run.result',
        data: {
          status: 'succeeded',
          version: { id: `v_${base + 1}`, name: 'Bigger captions', result_revision: base + 1 },
          summary: { done: ['Made 9 caption lines 20% bigger'], not_done: [] },
          suggestions: [],
          credits: credits(1, 1),
          duration_ms: 4800,
        },
      },
    },
    ...finishedVersion('Bigger captions', base + 1, 1235),
  ];
}

export function scenarioById(id: string): Scenario {
  return SCENARIOS.find((scenario) => scenario.id === id) ?? SCENARIOS[0];
}
