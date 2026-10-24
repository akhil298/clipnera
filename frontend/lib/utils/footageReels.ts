import type {
  EditChange, EditResolvedScriptMode, EditResponse, EditScriptMode, EditSourceResponse, EditStatus, EditTimelineResponse,
} from '@/lib/api';
import type { StatusTone } from '@/components/ui/StatusPill';

/** Mirrors reel_credits() in backend/edit_engine/pricing.py and its settings. */
export const EDIT_BASE_CREDITS = 6;
export const EDIT_OUTPUT_SECONDS_PER_CREDIT = 3;
export const EDIT_OPUS_CREDIT_MULTIPLIER = 1.5;

export const estimateEditCredits = (outputSeconds: number, rawSeconds: number, opus: boolean): number => {
  const credits = EDIT_BASE_CREDITS + Math.ceil(Math.max(0, outputSeconds) / EDIT_OUTPUT_SECONDS_PER_CREDIT)
    + Math.ceil(Math.max(0, rawSeconds) / 60);
  return opus ? Math.ceil(credits * EDIT_OPUS_CREDIT_MULTIPLIER) : credits;
};

export const EDIT_STATUS: Record<EditStatus, { tone: StatusTone; label: string }> = {
  draft: { tone: 'neutral', label: 'Draft' },
  analyzing: { tone: 'processing', label: 'Planning' },
  planned: { tone: 'scheduled', label: 'Plan ready' },
  rendering: { tone: 'processing', label: 'Rendering' },
  done: { tone: 'ready', label: 'Done' },
  failed: { tone: 'failed', label: 'Failed' },
};

export const SCRIPT_MODE_OPTIONS: [EditScriptMode, string][] = [
  ['auto', 'Decide for me'],
  ['spoken', 'I say this in the video'],
  ['voiceover', 'Read it as a voiceover'],
  ['onscreen', 'Show it as on-screen text'],
  ['direction', 'Just use it as direction'],
];

export const RESOLVED_SCRIPT_LABEL: Record<EditResolvedScriptMode, string> = {
  none: 'No script: the story comes from your footage',
  spoken: 'Following your script',
  voiceover: 'Your script is the voiceover',
  onscreen: 'Your script is on screen',
  direction: 'Your script is used as direction',
};

export const CONTENT_TYPE_LABEL: Record<string, string> = {
  talking_head: 'Talking head',
  montage: 'Montage',
  vlog: 'Vlog',
};

/** What a person sees while a reel is made: a few plain steps, never the engine's internal stages. */
export const EDIT_PHASES = [
  { label: 'Getting your video', minutes: 1 },
  { label: 'Watching your footage', minutes: 2 },
  { label: 'Finding the best moment', minutes: 2 },
  { label: 'Editing', minutes: 4 },
  { label: 'Final touches', minutes: 1 },
] as const;

// The reel engine's stages (reel_engine/pipeline.py STAGES) and the classic analysis's progress text
// (edit_engine/jobs.py) folded into those phases.
const PHASE_OF: Record<string, number> = {
  fetch: 0, queued: 1, ingest: 1, listen: 1, watch: 1, moments: 2, direct: 2, verify: 2, compile: 2,
  assets: 3, picture: 3, layout: 3, graphics: 3, sound: 3, compose: 3, review: 4, done: 4,
  'Fetching your YouTube video': 0, 'Waiting to start': 1, 'Reading your clips': 1, 'Listening to what you said': 1,
  'Finding the best takes': 1, 'Studying your reference reel': 1, 'Planning the edit': 2,
};

/** The steps this reel shows (fetching only for a YouTube link), the one under way, and roughly how long is left. */
export function editPhase(edit: EditResponse): { steps: string[]; active: number; minutesLeft: number } {
  const phases = edit.source_url ? EDIT_PHASES : EDIT_PHASES.slice(1);
  const offset = edit.source_url ? 0 : 1;
  const stages = edit.premium?.stages ?? [];
  const where = edit.status === 'rendering' ? 3
    : edit.engine === 'premium' ? PHASE_OF[stages.length ? stages[stages.length - 1].stage : 'queued'] ?? 1
    : PHASE_OF[edit.progress ?? 'Waiting to start'] ?? 1;
  const active = Math.min(phases.length - 1, Math.max(0, where - offset));
  const minutesLeft = Math.max(1, Math.round(phases.slice(active).reduce((sum, p, i) => sum + (i ? p.minutes : p.minutes / 2), 0)));
  return { steps: phases.map((p) => p.label), active, minutesLeft };
}

/** Mirrors MAX_SECONDS in backend/edit_engine/reference.py. */
export const REFERENCE_MAX_SECONDS = 180;

/** Reference links the backend can fetch (edit_engine/reference.py): YouTube videos and Shorts. */
export const isReferenceLink = (url: string): boolean =>
  /^https?:\/\/(www\.|m\.)?(youtube\.com\/(watch\?|shorts\/)|youtu\.be\/)\S+$/i.test(url.trim());

/** Instagram reel and post links (INSTAGRAM_LINK in backend/clip/instagram_service.py). */
export const isInstagramLink = (url: string): boolean =>
  /^https?:\/\/(www\.|m\.)?instagram\.com\/([\w.]+\/)?(reels?|p|tv)\/[\w-]+/i.test(url.trim());

/** Footage links the reel maker fetches: YouTube videos and Shorts, and Instagram reels. */
export const isSourceLink = (url: string): boolean => isReferenceLink(url) || isInstagramLink(url);

/** Mirrors the intent limit in backend/edit_engine/schema.py. */
export const INTENT_MAX = 300;

/** Briefs to start from; the AI still picks the format from the footage. */
export const BRIEF_STARTERS = [
  { title: 'Travel diary', hint: 'Best moments, fast cuts to the beat', sample: 'We made it',
    brief: 'A travel reel of the best moments. Open on the most exciting shot, cut fast to the music, captions on what I say.' },
  { title: 'Talking head', hint: 'Clean cuts, punchy hook, captions', sample: 'Stop doing this',
    brief: 'Keep my best takes, cut every pause and filler, open on my strongest line, and zoom in when a point lands.' },
  { title: 'Hype edit', hint: 'Zooms, pop-ups, high energy', sample: 'No way',
    brief: 'High energy: quick cuts, punch-ins on key words, pop-up words on the big moments, energetic music.' },
  { title: 'Product promo', hint: 'Show it, say why, call to action', sample: 'Meet the new',
    brief: 'Sell the product: show it early, keep the lines about why it is good, end on a clear call to action.' },
  { title: 'Podcast moment', hint: 'The best answer, nothing else', sample: 'Hot take',
    brief: 'Find the single best answer and keep only that, open on its boldest line, calm music under it.' },
  { title: 'Story explainer', hint: 'Calm pace, numbers on screen', sample: '3 things',
    brief: 'Tell it as a story at a calm pace, put numbers and key words on screen, end on the takeaway.' },
] as const;

/** One-tap additions to the brief. */
export const BRIEF_IDEAS = ['Hook in the first 2 seconds', 'Cut every pause', 'Calm, cinematic music', 'Zoom in on key words'];

export type BeatKind = 'camera' | 'broll' | 'photo' | 'card';

export interface Beat {
  index: number;
  kind: BeatKind;
  at: number;
  dur: number;
  /** What is said over it, from the captions' words. */
  line: string;
  source: EditSourceResponse | null;
  sourceStart: number;
  zoomed: boolean;
  pops: string[];
}

/** The reel as a list of shots, from the compiled timeline: what is on screen, when, and what is said over it. */
export function beatsFrom(timeline: EditTimelineResponse, sources: EditSourceResponse[]): Beat[] {
  return timeline.picture.map((item, index) => {
    const end = item.at + item.dur;
    const within = (start: number) => start >= item.at && start < end;
    // A video is on camera when its own sound plays under it; any other picture covers the voice.
    const ownVoice = timeline.voice.some((v) => v.src === item.src && v.at < end && v.at + (v.source_end - v.source_start) > item.at);
    const kind: BeatKind = item.kind === 'card' ? 'card' : item.kind === 'image' ? 'photo' : ownVoice ? 'camera' : 'broll';
    return {
      index, kind, at: item.at, dur: item.dur,
      line: item.kind === 'card' ? item.text ?? '' : timeline.words.filter((w) => within(w.start)).map((w) => w.word).join(' '),
      source: item.src === null ? null : sources[item.src] ?? null,
      sourceStart: item.source_start ?? 0,
      zoomed: (item.zoom ?? 1) > 1.01,
      pops: timeline.texts.filter((t) => t.kind === 'pop' && within(t.at)).map((t) => t.text),
    };
  });
}

/** What changed between two versions of a plan, and the changes that put the first one back. */
export function planDiff(before: EditResponse, after: EditResponse): { changed: string[]; undo: EditChange[] } {
  const a = before.plan;
  const b = after.plan;
  if (!a || !b) return { changed: [], undo: [] };
  const changed: string[] = [];
  const undo: EditChange[] = [];
  const check = (name: string, differs: boolean, change: EditChange) => {
    if (!differs) return;
    changed.push(name);
    undo.push(change);
  };
  check('hook', a.hook !== b.hook, { op: 'set_hook', value: a.hook });
  check('music', (a.music?.id ?? null) !== (b.music?.id ?? null), { op: 'set_music', value: a.music?.id ?? 'none' });
  check('look', a.look !== b.look, { op: 'set_look', value: a.look });
  check('captions', a.caption_style !== b.caption_style, { op: 'set_caption_style', value: a.caption_style });
  check('length', before.target_seconds !== after.target_seconds, { op: 'set_length', value: String(before.target_seconds) });
  check('missing lines', a.skip_missing !== b.skip_missing, { op: 'skip_missing_lines', value: String(a.skip_missing) });
  const wasOut = new Set(a.removed_lines.map((l) => l.id));
  const isOut = new Set(b.removed_lines.map((l) => l.id));
  const cut = [...isOut].filter((id) => !wasOut.has(id));
  const restored = [...wasOut].filter((id) => !isOut.has(id));
  if (cut.length || restored.length) changed.push('lines');
  undo.push(...cut.map((id): EditChange => ({ op: 'restore_line', value: id })),
    ...restored.map((id): EditChange => ({ op: 'remove_line', value: id })));
  if (a.pop_count !== b.pop_count) changed.push('pop-ups');
  return { changed, undo: undo.slice(0, 10) };
}

/** "hook, music and look" */
export const listWords = (words: string[]): string =>
  words.length < 2 ? words.join('') : `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`;

export const TARGET_OPTIONS = [0, 15, 30, 45, 60, 90] as const;

/** Browser-side duration of a video or audio file, so over-limit footage is refused before upload. */
export const mediaDuration = (file: File): Promise<number | null> =>
  new Promise((resolve) => {
    if (!file.type.startsWith('video/') && !file.type.startsWith('audio/')) {
      resolve(null);
      return;
    }
    const url = URL.createObjectURL(file);
    const media = document.createElement(file.type.startsWith('video/') ? 'video' : 'audio');
    media.preload = 'metadata';
    const done = (value: number | null) => {
      URL.revokeObjectURL(url);
      resolve(value);
    };
    media.onloadedmetadata = () => done(Number.isFinite(media.duration) ? media.duration : null);
    media.onerror = () => done(null);
    media.src = url;
  });

export const formatSeconds = (s: number): string =>
  `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
