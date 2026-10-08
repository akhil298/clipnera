/**
 * What is on screen and audible at a moment of a Timeline v1: the clips per
 * layer (with keyframes and transitions worked out), B-roll, text, the hook and
 * the caption line. Pure, so the preview, the timeline and the transcript all
 * agree on the same answer, and `node --test` runs it directly.
 *
 * Times in and out are timeline seconds; the document itself counts frames.
 */
import { itemFrames } from '../editor/timeline';
import type { Asset, ClipItem, Item, Keyframe, KeyframeProp, MusicItem, SfxItem, TextItem, Timeline, Track, Transform } from '../editor/timeline';

/** On-screen text roles; the reel adapter files these as the text item's `style`. */
export type TextRole = 'hook' | 'pop' | 'line' | 'card' | 'text';

export interface CaptionWord {
  text: string;
  /** Timeline seconds. */
  start: number;
  end: number;
}

export interface ActiveClip {
  track: Track;
  item: ClipItem;
  asset: Asset;
  /** Where the source should be, in source seconds. */
  sourceTime: number;
  /** Frames since the item started. */
  localFrame: number;
  /** The item's transform with its keyframes applied at this frame. */
  transform: Transform;
  opacity: number;
  /** The way in, while it is still running. */
  transition: { type: 'fade' | 'slide_left' | 'zoom'; progress: number } | null;
}

export interface ActiveText {
  track: Track;
  item: TextItem;
  role: TextRole;
  /** 0 at the item's first frame, 1 at its end. */
  progress: number;
}

export interface CaptionLine {
  words: CaptionWord[];
  /** Index in `words` of the word being spoken, or -1 between words. */
  activeIndex: number;
  style: string;
}

export interface OverlayFrame {
  frame: number;
  /** Every visible clip, bottom layer first (video tracks, then overlay tracks, in track order). */
  layers: ActiveClip[];
  /** The top video-track clip: the picture everything else sits on. */
  base: ActiveClip | null;
  /** Clips on overlay tracks. */
  broll: ActiveClip[];
  texts: ActiveText[];
  hook: ActiveText | null;
  caption: CaptionLine | null;
}

export interface OverlayOptions {
  /** Caption words in timeline seconds (from the transcript); captions show only when given. */
  words?: readonly CaptionWord[];
  /** Most words on one caption line. Default 3, as the reel preview and burner group them. */
  wordsPerLine?: number;
  /** Slides and zooms in become fades. */
  reducedMotion?: boolean;
}

const KEYFRAME_PROPS: readonly KeyframeProp[] = ['x', 'y', 'scale', 'rotation', 'opacity'];
const TEXT_ROLES: readonly TextRole[] = ['hook', 'pop', 'line', 'card'];
/** Mirrors PHRASE_PAUSE_SECONDS and CLAUSE_ENDINGS in the ASS burner (and the clip studio preview). */
const PHRASE_PAUSE_SECONDS = 0.35;
const CLAUSE_ENDING = /[.,?!;:…]$/;
/** A word stays lit this long after it ends, unless the next one has started (reel preview behaviour). */
const WORD_LINGER_SECONDS = 0.25;

/** The item covering `frame` on a track whose items are sorted by `at`; binary search. */
export function itemAt<T extends Item>(items: readonly T[], frame: number): T | null {
  let lo = 0;
  let hi = items.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const item = items[mid];
    if (frame < item.at) hi = mid - 1;
    else if (frame >= item.at + itemFrames(item)) lo = mid + 1;
    else return item;
  }
  return null;
}

/** The first item starting after `frame`. */
export function itemAfter<T extends Item>(items: readonly T[], frame: number): T | null {
  return items.find((item) => item.at > frame) ?? null;
}

const EASE: Record<Keyframe['ease'], (x: number) => number> = {
  linear: (x) => x,
  in: (x) => x * x,
  out: (x) => 1 - (1 - x) * (1 - x),
  in_out: (x) => (x < 0.5 ? 2 * x * x : 1 - 2 * (1 - x) * (1 - x)),
};

/**
 * A keyframed value at `frame` (relative to the item). Held flat before the first
 * and after the last point; the ease of the point being left shapes each segment.
 */
export function keyframeValue(points: readonly Keyframe[] | undefined, frame: number, fallback: number): number {
  if (!points?.length) return fallback;
  const sorted = [...points].sort((a, b) => a.f - b.f);
  if (frame <= sorted[0].f) return sorted[0].v;
  for (let i = 1; i < sorted.length; i++) {
    const [a, b] = [sorted[i - 1], sorted[i]];
    if (frame <= b.f) return a.v + (b.v - a.v) * EASE[a.ease]((frame - a.f) / (b.f - a.f));
  }
  return sorted[sorted.length - 1].v;
}

/** Source seconds shown at timeline second `time` by a clip. */
export const sourceTimeAt = (clip: ClipItem, time: number, fps: number): number =>
  clip.src_in / fps + (time - clip.at / fps) * clip.speed;

function activeClip(timeline: Timeline, track: Track, clip: ClipItem, time: number, frame: number, reducedMotion: boolean): ActiveClip | null {
  const asset = timeline.assets[clip.asset];
  if (!asset) return null;
  const localFrame = frame - clip.at;
  const value = (prop: KeyframeProp, base: number) => keyframeValue(clip.keyframes[prop], localFrame, base);
  const [x, y, scale, rotation, opacity] = KEYFRAME_PROPS.map((prop) =>
    value(prop, prop === 'opacity' ? 1 : clip.transform[prop as keyof Transform]));
  const way = clip.transition_in;
  const running = way && way.type !== 'cut' && way.frames > 0 && localFrame < way.frames;
  return {
    track, item: clip, asset, localFrame,
    sourceTime: asset.kind === 'image' ? 0 : sourceTimeAt(clip, time, timeline.fps),
    transform: { x, y, scale, rotation },
    opacity,
    transition: running
      ? { type: reducedMotion && way.type !== 'fade' ? 'fade' : (way.type as 'fade' | 'slide_left' | 'zoom'), progress: localFrame / way.frames }
      : null,
  };
}

/** Caption lines as the burner breaks them: at most `max` words, broken after a clause or a pause. */
export function groupCaptionWords(words: readonly CaptionWord[], max = 3): CaptionWord[][] {
  const lines: CaptionWord[][] = [];
  let line: CaptionWord[] = [];
  for (const word of words) {
    const previous = line[line.length - 1];
    const breaks = previous && (CLAUSE_ENDING.test(previous.text.trim()) || word.start - previous.end >= PHRASE_PAUSE_SECONDS);
    if (line.length >= Math.max(1, max) || breaks) {
      lines.push(line);
      line = [];
    }
    line.push(word);
  }
  if (line.length) lines.push(line);
  return lines;
}

/** The caption line showing at `time` and its lit word; null between lines. */
export function captionAt(words: readonly CaptionWord[], time: number, max = 3): Omit<CaptionLine, 'style'> | null {
  for (const line of groupCaptionWords(words, max)) {
    const last = line[line.length - 1];
    if (time < line[0].start) return null;
    if (time >= last.end + WORD_LINGER_SECONDS) continue;
    const activeIndex = line.findIndex((w, i) => {
      const next = line[i + 1];
      return time >= w.start && time < Math.min(w.end + WORD_LINGER_SECONDS, next ? next.start : Infinity);
    });
    return { words: line, activeIndex };
  }
  return null;
}

export const textRole = (item: TextItem): TextRole =>
  (TEXT_ROLES as readonly string[]).includes(item.style) ? (item.style as TextRole) : 'text';

/** Everything on screen at timeline second `time`. */
export function evaluateOverlays(timeline: Timeline, time: number, options: OverlayOptions = {}): OverlayFrame {
  const frame = Math.floor(time * timeline.fps + 1e-6);
  const reducedMotion = options.reducedMotion ?? false;
  const visual = (kind: Track['kind']) => timeline.tracks.filter((t) => t.kind === kind).flatMap((track) => {
    const item = itemAt(track.items, frame);
    const clip = item?.type === 'clip' ? activeClip(timeline, track, item, time, frame, reducedMotion) : null;
    return clip ? [clip] : [];
  });
  const video = visual('video');
  const broll = visual('overlay');
  const texts = timeline.tracks.filter((t) => t.kind === 'text').flatMap((track) => {
    const item = itemAt(track.items, frame);
    return item?.type === 'text' ? [{ track, item, role: textRole(item), progress: (frame - item.at) / item.dur }] : [];
  });
  const captions = timeline.captions;
  const line = captions?.enabled && options.words?.length ? captionAt(options.words, time, options.wordsPerLine) : null;
  return {
    frame,
    layers: [...video, ...broll],
    base: video[video.length - 1] ?? null,
    broll,
    texts,
    hook: texts.find((t) => t.role === 'hook') ?? null,
    caption: line && captions ? { ...line, style: captions.style } : null,
  };
}

/** Sound effects whose start falls in (from, to], for firing cues as playback passes them. */
export function cuesBetween(timeline: Timeline, from: number, to: number): SfxItem[] {
  if (to <= from) return [];
  const [a, b] = [from * timeline.fps, to * timeline.fps];
  return timeline.tracks
    .filter((t) => t.kind === 'audio' && !t.muted)
    .flatMap((t) => t.items.filter((i): i is SfxItem => i.type === 'sfx' && i.at > a && i.at <= b));
}

export interface AudibleItem {
  track: Track;
  item: ClipItem | MusicItem;
  /** Source seconds (a clip) or seconds into the music track. */
  sourceTime: number;
  /** Linear gain, 0..2. */
  gain: number;
}

/**
 * The preview's stand-in for the render's sidechain ducking (render.py: ratio 8):
 * music drops this much while speech plays. Close, not exact.
 */
export const DUCK_DB = -10;
export const dbToGain = (db: number): number => 10 ** (db / 20);

/** What plays on the audio tracks at `time`. Picture tracks stay silent, as in the reel preview. */
export function audibleAt(timeline: Timeline, time: number): AudibleItem[] {
  const frame = Math.floor(time * timeline.fps + 1e-6);
  const playing = timeline.tracks.filter((t) => t.kind === 'audio' && !t.muted).flatMap((track) => {
    const item = itemAt(track.items, frame);
    return item && (item.type === 'clip' || item.type === 'music') ? [{ track, item }] : [];
  });
  const speech = playing.some(({ item }) => item.type === 'clip');
  return playing.map(({ track, item }) => item.type === 'clip'
    ? { track, item, sourceTime: sourceTimeAt(item, time, timeline.fps), gain: item.volume }
    : { track, item, sourceTime: (item.offset - item.at) / timeline.fps + time,
        gain: dbToGain(item.gain_db + (item.duck && speech ? DUCK_DB : 0)) });
}
