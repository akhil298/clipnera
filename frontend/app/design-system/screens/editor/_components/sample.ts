/**
 * Hard-coded sample data for the Editor mockups. Nothing here is fetched; the
 * names are invented. Times are seconds for readability; the real Timeline v1
 * contract is in frames (events.md §3.2).
 */

import type { BrollShot } from '@/components/ui/BrollPick';
import type { PromptContext } from '@/components/ui/ContextChip';

export const PROJECT = {
  id: 'p_demo',
  title: 'Kavya on pricing',
  source: 'kavya-interview.mov',
  sourceLength: '12:40',
  aspect: '9:16',
};

export const CLIP = {
  id: 'c_7',
  title: 'Why ₹499 works',
  index: 3,
  total: 12,
};

export type LaneKind = 'title' | 'video' | 'captions' | 'broll' | 'music' | 'speech';

export interface Lane {
  id: LaneKind;
  label: string;
}

/** Lanes top to bottom. The studio's "Sound" lane is gone with the Sound panel (Removals and moves). */
export const LANES: ReadonlyArray<Lane> = [
  { id: 'title', label: 'Title' },
  { id: 'video', label: 'Video' },
  { id: 'captions', label: 'Captions' },
  { id: 'broll', label: 'B-roll' },
  { id: 'music', label: 'Music' },
  { id: 'speech', label: 'Speech' },
];

export interface TimelineBlock {
  id: string;
  lane: LaneKind;
  start: number;
  end: number;
  label: string;
  /** Hatched span: a silence or a cut the user can restore. */
  cut?: boolean;
}

const silences: TimelineBlock[] = [
  [3.1, 5.2], [8.4, 11.9], [14.2, 16.0], [19.5, 23.1], [26.0, 27.4], [30.2, 33.8], [36.1, 38.0],
  [41.3, 44.9], [47.0, 48.6], [51.2, 54.5], [57.0, 58.8], [61.5, 64.6], [66.2, 67.9], [69.4, 71.6],
].map(([start, end], index) => ({ id: `s${index + 1}`, lane: 'video', start, end, label: 'Silence', cut: true }));

const BEFORE: TimelineBlock[] = [
  { id: 't1', lane: 'title', start: 0, end: 5, label: 'Why ₹499 works' },
  { id: 'v1', lane: 'video', start: 0, end: 24, label: 'Opening' },
  { id: 'v2', lane: 'video', start: 24, end: 50, label: 'The price' },
  { id: 'v3', lane: 'video', start: 50, end: 72, label: 'The close' },
  ...silences,
  { id: 'm1', lane: 'music', start: 0, end: 72, label: 'Calm piano · ducked' },
  { id: 'sp', lane: 'speech', start: 0, end: 72, label: 'Speech' },
];

const TRIMMED: TimelineBlock[] = [
  { id: 't1', lane: 'title', start: 0, end: 5, label: 'Why ₹499 works' },
  { id: 'v1', lane: 'video', start: 0, end: 9.6, label: 'Opening' },
  { id: 'v2', lane: 'video', start: 9.6, end: 19.8, label: 'The price' },
  { id: 'v3', lane: 'video', start: 19.8, end: 30, label: 'The close' },
  { id: 'm1', lane: 'music', start: 0, end: 30, label: 'Calm piano · ducked' },
  { id: 'sp', lane: 'speech', start: 0, end: 30, label: 'Speech' },
];

const CAPTION_LINES = ['So here is', 'why we priced', 'it at ₹499', 'a month', 'less than', 'two coffees', 'and people', 'actually stay', 'for a year'];

const CAPTIONED: TimelineBlock[] = [
  ...TRIMMED,
  ...CAPTION_LINES.map((label, index) => ({
    id: `cap${index + 1}`,
    lane: 'captions' as const,
    start: index * 3.3,
    end: index * 3.3 + 3.1,
    label,
  })),
];

const WITH_BROLL: TimelineBlock[] = [...CAPTIONED, { id: 'b1', lane: 'broll', start: 12, end: 16, label: 'Pouring coffee' }];

/** The timeline at each revision the sample run produces (events.md §9 numbering). */
export const REVISIONS: Record<number, ReadonlyArray<TimelineBlock>> = {
  40: BEFORE,
  41: TRIMMED,
  42: CAPTIONED,
  43: WITH_BROLL,
};

export const CAPTION_IDS = CAPTION_LINES.map((_, index) => `cap${index + 1}`);

export const VIEW_SECONDS = 75;

export interface Word {
  id: string;
  text: string;
  start: number;
  filler?: boolean;
}

const SCRIPT =
  'So um here is why we priced it at ₹499 a month. It is less than like two coffees, and people actually stay for a year. We tried ₹999 first and uh nobody converted.';

export const WORDS: ReadonlyArray<Word> = SCRIPT.split(' ').map((text, index) => ({
  id: `w${index}`,
  text,
  start: index * 0.9,
  filler: ['um', 'like', 'uh'].includes(text),
}));

export interface VersionRow {
  id: string;
  name: string;
  author: 'You' | 'Clipnera';
  time: string;
  exact: string;
  current?: boolean;
  bookmarked?: boolean;
  /** Restores and undo create a new version that names its source. */
  kind?: 'ai_run' | 'hand' | 'restore';
}

export const VERSIONS: ReadonlyArray<VersionRow> = [
  { id: 'v12', name: 'Trimmed silences, added captions', author: 'Clipnera', time: 'Just now', exact: '3 Oct 2026, 14:05', current: true, kind: 'ai_run' },
  { id: 'v11', name: 'Moved the title down', author: 'You', time: '6 min ago', exact: '3 Oct 2026, 13:59', kind: 'hand' },
  { id: 'v10', name: 'Added B-roll at 0:12', author: 'Clipnera', time: '22 min ago', exact: '3 Oct 2026, 13:43', bookmarked: true, kind: 'ai_run' },
  { id: 'v9', name: 'Restored “First cut”', author: 'You', time: '1 hour ago', exact: '3 Oct 2026, 13:01', kind: 'restore' },
  { id: 'v8', name: 'Punchier hook', author: 'Clipnera', time: '2 hours ago', exact: '3 Oct 2026, 12:10', kind: 'ai_run' },
  { id: 'v1', name: 'First cut', author: 'Clipnera', time: '2 Oct', exact: '2 Oct 2026, 18:22', bookmarked: true, kind: 'ai_run' },
];

export const CHIP_CLIP: PromptContext = { id: 'ctx-clip', kind: 'clip', label: CLIP.title, meta: '1:12' };
export const CHIP_RANGE: PromptContext = { id: 'ctx-range', kind: 'range', label: '0:12 – 0:16' };
export const CHIP_CAPTION: PromptContext = { id: 'ctx-caption', kind: 'caption', label: '“less than two coffees”' };
export const CHIP_ASSET: PromptContext = { id: 'ctx-asset', kind: 'asset', label: 'Pouring coffee', meta: '0:06' };
export const CHIP_MOMENT: PromptContext = { id: 'ctx-moment', kind: 'moment', label: '0:21' };

export interface ClipRow {
  id: string;
  title: string;
  range: string;
  length: string;
  score: number;
  hook: string;
  hookScore: number;
  engage: number;
  /** Two-stop neutral gradient standing in for the poster; no external images. */
  tone: number;
}

export const CLIPS: ReadonlyArray<ClipRow> = [
  { id: 'c1', title: 'The ₹999 mistake', range: '2:14 – 2:58', length: '0:44', score: 94, hook: 'We tried ₹999 first and nobody converted.', hookScore: 91, engage: 88, tone: 0 },
  { id: 'c2', title: 'Cheaper than two coffees', range: '4:02 – 4:31', length: '0:29', score: 91, hook: 'It costs less than two coffees a month.', hookScore: 86, engage: 90, tone: 1 },
  { id: 'c3', title: 'Why ₹499 works', range: '5:40 – 6:52', length: '1:12', score: 88, hook: 'Here is why we priced it at ₹499.', hookScore: 82, engage: 84, tone: 2 },
  { id: 'c4', title: 'People stay for a year', range: '7:10 – 7:46', length: '0:36', score: 85, hook: 'People actually stay for a year.', hookScore: 79, engage: 86, tone: 3 },
  { id: 'c5', title: 'Pricing is a promise', range: '9:01 – 9:40', length: '0:39', score: 81, hook: 'Your price is a promise to the customer.', hookScore: 77, engage: 80, tone: 4 },
  { id: 'c6', title: 'Do not discount', range: '10:12 – 10:44', length: '0:32', score: 76, hook: 'Never discount in your first year.', hookScore: 74, engage: 72, tone: 5 },
];

/** B-roll shots in the `components/ui` BrollShot shape; durations in seconds, no posters (no external images). */
export const BROLL_ALTERNATES: ReadonlyArray<BrollShot> = [
  { id: 'b_2', title: 'Coffee cup on a desk', duration: 5, source: 'Clipnera library' },
  { id: 'b_3', title: 'Café counter, Mumbai', duration: 8, source: 'Clipnera library' },
  { id: 'b_4', title: 'Filter coffee pour', duration: 4, source: 'Your uploads' },
  { id: 'b_5', title: 'Two cups clinking', duration: 6, source: 'Clipnera library' },
];

/** The shot the sample run placed. */
export const BROLL_PLACED: BrollShot = { id: 'b_1', title: 'Pouring coffee into a white mug', duration: 4, source: 'your uploads' };
export const BROLL_REASONS = ['matches “coffee” and “pour”', 'from your library', 'fits 9:16'];

/** Neutral poster tones: footage stand-ins that stay on palette. */
export const POSTER_TONES = [
  'from-cn-surface-active to-cn-bg',
  'from-cn-surface-hover to-cn-surface',
  'from-cn-border-strong to-cn-bg',
  'from-cn-surface to-cn-surface-active',
  'from-cn-surface-active to-cn-surface',
  'from-cn-border-strong to-cn-surface',
];

export function clock(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
