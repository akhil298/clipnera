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

/** The progress steps the analysis reports, in order (see backend edit_engine/jobs.py). */
export const analysisSteps = (withReference: boolean): string[] => [
  'Reading your clips',
  'Listening to what you said',
  'Finding the best takes',
  ...(withReference ? ['Studying your reference reel'] : []),
  'Planning the edit',
];

/** The reel engine's stages (backend reel_engine/pipeline.py STAGES), as the progress list shows them. */
export const PREMIUM_STEPS: [string, string][] = [
  ['ingest', 'Reading your files'],
  ['listen', 'Listening for voice, music and words'],
  ['watch', 'Watching every shot'],
  ['direct', 'Directing the story'],
  ['verify', 'Checking hooks and labels against the footage'],
  ['compile', 'Building the timeline'],
  ['assets', 'Finding and making assets'],
  ['picture', 'Cutting, framing and grading'],
  ['layout', 'Placing graphics off faces and the action'],
  ['graphics', 'Animating graphics and captions'],
  ['sound', 'Mixing voice, music and effects'],
  ['compose', 'Final encode'],
  ['review', 'Head-editor review'],
];

/** The ten premium layers the review scores (backend reel_engine/plan.py LAYERS). */
export const PREMIUM_LAYERS: Record<string, string> = {
  selection: 'Selection', hook: 'Hook', story: 'Story', picture: 'Picture', rhythm: 'Rhythm',
  captions: 'Captions', graphics: 'Motion graphics', depth: 'Depth', sound: 'Sound', finish: 'Finish',
};

export const RECIPE_NAMES: Record<string, string> = {
  creator_advice: 'Creator advice', interview: 'Interview', voice_food: 'Talking while cooking', vlog: 'Vlog',
  recipe_process: 'Recipe / process', local_ad: 'Local business ad', explainer: 'Explainer', product_demo: 'Product demo',
};

export const AUDIO_NAMES: Record<string, string> = {
  voice: 'Your voice', song: 'A song (replaced with our own score)', voice_song: 'Your voice over music (music replaced)', silent: 'No audio',
};

/** Mirrors MAX_SECONDS in backend/edit_engine/reference.py. */
export const REFERENCE_MAX_SECONDS = 180;

/** Reference links the backend can fetch (edit_engine/reference.py): YouTube videos and Shorts. */
export const isReferenceLink = (url: string): boolean =>
  /^https?:\/\/(www\.|m\.)?(youtube\.com\/(watch\?|shorts\/)|youtu\.be\/)\S+$/i.test(url.trim());

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
