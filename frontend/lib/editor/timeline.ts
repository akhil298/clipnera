/**
 * Timeline v1 and the operations that change it. Mirrors backend/editor/timeline.py
 * and backend/editor/ops.py field for field; backend/editor/fixtures/timeline_ops.json
 * is run against both, so the browser and the server always apply an edit the same way.
 *
 * Time is whole frames at the timeline's fps. Nothing here imports anything, so
 * Node runs the tests on this file directly (`npm test`).
 */

export type TrackKind = 'video' | 'overlay' | 'text' | 'audio';
export type KeyframeProp = 'x' | 'y' | 'scale' | 'rotation' | 'opacity';

export interface Asset {
  id: string;
  kind: 'video' | 'image' | 'audio';
  key: string;
  proxy: string | null;
  /** Length in timeline frames; an image is 1 frame and stretches to any length. */
  frames: number;
  width: number | null;
  height: number | null;
  has_audio: boolean;
}

/**
 * Placement as shares of the frame. On a clip, x/y is the point of the source kept at the
 * centre of the frame and scale zooms in on top of filling it; on text, x/y is where its centre sits.
 */
export interface Transform {
  x: number;
  y: number;
  scale: number;
  rotation: number;
}

export interface Keyframe {
  /** Frame relative to the item's start. */
  f: number;
  v: number;
  ease: 'linear' | 'in' | 'out' | 'in_out';
}

export interface Transition {
  type: 'cut' | 'fade' | 'slide_left' | 'zoom';
  frames: number;
}

export interface ClipItem {
  type: 'clip';
  id: string;
  at: number;
  asset: string;
  src_in: number;
  src_out: number;
  speed: number;
  volume: number;
  transform: Transform;
  keyframes: Partial<Record<KeyframeProp, Keyframe[]>>;
  transition_in: Transition | null;
}

export interface TextItem {
  type: 'text';
  id: string;
  at: number;
  text: string;
  style: string;
  dur: number;
  transform: Transform;
}

export interface MusicItem {
  type: 'music';
  id: string;
  at: number;
  /** A music library track id. */
  track: string;
  dur: number;
  offset: number;
  gain_db: number;
  duck: boolean;
}

export interface SfxItem {
  type: 'sfx';
  id: string;
  at: number;
  name: string;
  dur: number;
  gain_db: number;
}

export type Item = ClipItem | TextItem | MusicItem | SfxItem;

export interface Track {
  id: string;
  kind: TrackKind;
  items: Item[];
  muted: boolean;
}

export interface Captions {
  enabled: boolean;
  style: string;
  language: string;
  /** The video or audio track whose speech the captions show. */
  follow: string;
}

export interface Marker {
  f: number;
  label: string;
}

export interface Timeline {
  version: 1;
  fps: 24 | 25 | 30 | 60;
  width: number;
  height: number;
  look: string;
  assets: Record<string, Asset>;
  tracks: Track[];
  captions: Captions | null;
  markers: Marker[];
}

export interface ItemPatch {
  speed?: number;
  volume?: number;
  transform?: Partial<Transform>;
  keyframes?: Partial<Record<KeyframeProp, Keyframe[]>>;
  transition_in?: Transition;
  text?: string;
  style?: string;
  dur?: number;
  offset?: number;
  gain_db?: number;
  duck?: boolean;
}

export type TimelineOp =
  | { op: 'add_track'; id: string; kind: TrackKind }
  | { op: 'add_item'; track: string; item: Item }
  | { op: 'remove_item'; item: string; ripple?: boolean }
  | { op: 'move_item'; item: string; at: number; track?: string | null }
  | { op: 'trim_item'; item: string; src_in?: number | null; src_out?: number | null }
  | { op: 'split_item'; item: string; at: number; new_id: string }
  | { op: 'update_item'; item: string; patch: ItemPatch }
  | { op: 'replace_asset'; item: string; asset: string }
  | { op: 'add_asset'; asset: Asset }
  | { op: 'set_captions'; enabled?: boolean; style?: string; language?: string; follow?: string }
  | { op: 'set_project'; look?: string; width?: number; height?: number }
  | { op: 'add_marker'; marker: Marker }
  | { op: 'remove_marker'; f: number };

/** A Timeline or an operation broke a rule; `code` matches the backend's TimelineError. */
export class TimelineError extends Error {
  code: string;
  opIndex: number | null = null;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'TimelineError';
    this.code = code;
  }
}

const TRACK_ITEMS: Record<TrackKind, ReadonlyArray<Item['type']>> = {
  video: ['clip'],
  overlay: ['clip'],
  text: ['text'],
  audio: ['clip', 'music', 'sfx'],
};

const DEFAULT_CAPTION_STYLE = 'karaoke';
const DEFAULT_TRANSFORM: Transform = { x: 0.5, y: 0.5, scale: 1, rotation: 0 };

/** Which patch fields each item type has, with the range the backend accepts. */
type Rule = { min?: number; max?: number; above?: number; kind: 'number' | 'int' | 'text' | 'bool' | 'object' };
const PATCH_RULES: Record<Item['type'], Partial<Record<keyof ItemPatch, Rule>>> = {
  clip: {
    speed: { kind: 'number', min: 0.25, max: 4 },
    volume: { kind: 'number', min: 0, max: 2 },
    transform: { kind: 'object' },
    keyframes: { kind: 'object' },
    transition_in: { kind: 'object' },
  },
  text: { text: { kind: 'text', min: 1, max: 200 }, style: { kind: 'text', min: 1, max: 60 }, dur: { kind: 'int', min: 1 }, transform: { kind: 'object' } },
  music: { dur: { kind: 'int', min: 1 }, offset: { kind: 'int', min: 0 }, gain_db: { kind: 'number', min: -60, max: 12 }, duck: { kind: 'bool' } },
  sfx: { dur: { kind: 'int', min: 1 }, gain_db: { kind: 'number', min: -60, max: 12 } },
};
const TRANSFORM_RULES: Record<keyof Transform, Rule> = {
  x: { kind: 'number', min: -1, max: 2 },
  y: { kind: 'number', min: -1, max: 2 },
  scale: { kind: 'number', above: 0, max: 10 },
  rotation: { kind: 'number', min: -360, max: 360 },
};

/** Round half up; the backend's to_frames does the same. */
export const toFrames = (value: number): number => Math.floor(value + 0.5);

export const itemFrames = (item: Item): number =>
  item.type === 'clip' ? toFrames((item.src_out - item.src_in) / item.speed) : item.dur;

export const itemEnd = (item: Item): number => item.at + itemFrames(item);

export const duration = (timeline: Timeline): number =>
  Math.max(0, ...timeline.tracks.flatMap((track) => track.items.map(itemEnd)));

/** Fill every default, so a Timeline from the API (which omits defaults) has every field set. */
export function normalise(raw: unknown): Timeline {
  const t = raw as Partial<Timeline> & { tracks?: Array<Partial<Track>>; assets?: Record<string, Partial<Asset>> };
  return {
    version: 1,
    fps: t.fps ?? 30,
    width: t.width ?? 1080,
    height: t.height ?? 1920,
    look: t.look ?? 'natural',
    assets: Object.fromEntries(Object.entries(t.assets ?? {}).map(([key, a]) => [key, normaliseAsset(a)])),
    tracks: (t.tracks ?? []).map((track) => ({
      id: track.id as string,
      kind: track.kind as TrackKind,
      items: (track.items ?? []).map(normaliseItem),
      muted: track.muted ?? false,
    })),
    captions: t.captions
      ? { enabled: t.captions.enabled ?? true, style: t.captions.style ?? DEFAULT_CAPTION_STYLE, language: t.captions.language ?? 'en', follow: t.captions.follow }
      : null,
    markers: (t.markers ?? []).map((m) => ({ f: m.f, label: m.label })),
  };
}

function normaliseAsset(a: Partial<Asset>): Asset {
  return {
    id: a.id as string, kind: a.kind as Asset['kind'], key: a.key as string, proxy: a.proxy ?? null,
    frames: a.frames as number, width: a.width ?? null, height: a.height ?? null, has_audio: a.has_audio ?? false,
  };
}

/** Any item's fields, each optional, as an API payload may carry them. */
type LooseItem = { type: Item['type'] } & Partial<Omit<ClipItem, 'type'>> & Partial<Omit<TextItem, 'type'>>
  & Partial<Omit<MusicItem, 'type'>> & Partial<Omit<SfxItem, 'type'>>;

function normaliseItem(raw: Partial<Item>): Item {
  const i = raw as LooseItem;
  const transform = { ...DEFAULT_TRANSFORM, ...(i.transform ?? {}) };
  switch (i.type) {
    case 'clip':
      return {
        type: 'clip', id: i.id!, at: i.at!, asset: i.asset!, src_in: i.src_in!, src_out: i.src_out!,
        speed: i.speed ?? 1, volume: i.volume ?? 1, transform,
        keyframes: Object.fromEntries(Object.entries(i.keyframes ?? {}).map(([prop, points]) => [
          prop, (points ?? []).map((p) => ({ f: p.f, v: p.v, ease: p.ease ?? 'linear' })),
        ])),
        transition_in: i.transition_in ? { type: i.transition_in.type ?? 'cut', frames: i.transition_in.frames ?? 0 } : null,
      };
    case 'text':
      return { type: 'text', id: i.id!, at: i.at!, text: i.text!, style: i.style!, dur: i.dur!, transform };
    case 'music':
      return { type: 'music', id: i.id!, at: i.at!, track: i.track!, dur: i.dur!, offset: i.offset ?? 0, gain_db: i.gain_db ?? -20, duck: i.duck ?? true };
    case 'sfx':
      return { type: 'sfx', id: i.id!, at: i.at!, name: i.name!, dur: i.dur!, gain_db: i.gain_db ?? 0 };
  }
}

function findTrack(doc: Timeline, trackId: string): Track {
  const track = doc.tracks.find((t) => t.id === trackId);
  if (!track) throw new TimelineError('UNKNOWN_TRACK', `There is no track ${trackId}.`);
  return track;
}

export function findItem(doc: Timeline, itemId: string): [Track, Item] {
  for (const track of doc.tracks) {
    const item = track.items.find((i) => i.id === itemId);
    if (item) return [track, item];
  }
  throw new TimelineError('UNKNOWN_ITEM', `There is no item ${itemId}.`);
}

/** Throw TimelineError on the first rule the Timeline breaks; the same order as the backend. */
export function check(doc: Timeline): void {
  for (const [key, asset] of Object.entries(doc.assets)) {
    if (key !== asset.id) throw new TimelineError('DUPLICATE_ID', `Asset ${asset.id} is filed under ${key}.`);
  }
  const seen = new Set<string>();
  for (const track of doc.tracks) {
    if (seen.has(track.id)) throw new TimelineError('DUPLICATE_ID', `Two tracks are called ${track.id}.`);
    seen.add(track.id);
  }
  for (const track of doc.tracks) {
    let previous: Item | null = null;
    for (const item of [...track.items].sort((a, b) => a.at - b.at)) {
      if (seen.has(item.id)) throw new TimelineError('DUPLICATE_ID', `Two things are called ${item.id}.`);
      seen.add(item.id);
      checkItem(doc, track, item);
      if (previous && item.at < itemEnd(previous)) {
        throw new TimelineError('OVERLAP', `${item.id} overlaps ${previous.id} on track ${track.id}.`);
      }
      previous = item;
    }
  }
  const followed = doc.captions && doc.tracks.find((t) => t.id === doc.captions!.follow);
  if (doc.captions && !(followed && (followed.kind === 'video' || followed.kind === 'audio'))) {
    throw new TimelineError('UNKNOWN_TRACK', `Captions follow ${doc.captions.follow}, which has no speech.`);
  }
}

function checkItem(doc: Timeline, track: Track, item: Item): void {
  if (!TRACK_ITEMS[track.kind].includes(item.type)) {
    throw new TimelineError('WRONG_TRACK', `A ${item.type} can't go on the ${track.kind} track ${track.id}.`);
  }
  if (item.type !== 'clip') return;
  const asset = doc.assets[item.asset];
  if (!asset) throw new TimelineError('UNKNOWN_ASSET', `${item.id} uses ${item.asset}, which isn't in the project.`);
  if (track.kind === 'audio' && !(asset.kind === 'audio' || asset.has_audio)) {
    throw new TimelineError('WRONG_TRACK', `${asset.id} has no sound to put on the audio track.`);
  }
  if (track.kind !== 'audio' && asset.kind === 'audio') {
    throw new TimelineError('WRONG_TRACK', `${asset.id} is audio only and can't be shown.`);
  }
  if (item.src_out <= item.src_in || (asset.kind !== 'image' && item.src_out > asset.frames)) {
    throw new TimelineError('OUT_OF_RANGE', `${item.id} plays frames ${item.src_in}-${item.src_out} of a ${asset.frames}-frame asset.`);
  }
  const length = itemFrames(item);
  for (const [prop, points] of Object.entries(item.keyframes)) {
    if ((points ?? []).some((p) => p.f > length)) {
      throw new TimelineError('OUT_OF_RANGE', `A ${prop} keyframe on ${item.id} is past its end.`);
    }
  }
}

/**
 * Apply `ops` in order to a copy of `timeline`; nothing changes if any op fails.
 * The thrown error's `opIndex` names the op that failed.
 */
export function applyOps(timeline: Timeline, ops: readonly TimelineOp[]): Timeline {
  const doc = structuredClone(timeline);
  ops.forEach((op, index) => {
    try {
      APPLY[op.op](doc, op as never);
      for (const track of doc.tracks) track.items.sort((a, b) => a.at - b.at);
      check(doc);
    } catch (error) {
      if (error instanceof TimelineError) error.opIndex = index;
      throw error;
    }
  });
  return doc;
}

type Applier<K extends TimelineOp['op']> = (doc: Timeline, op: Extract<TimelineOp, { op: K }>) => void;

const asClip = (doc: Timeline, itemId: string): ClipItem => {
  const [, item] = findItem(doc, itemId);
  if (item.type !== 'clip') throw new TimelineError('WRONG_ITEM_TYPE', `${itemId} is a ${item.type}, not a clip.`);
  return item;
};

/** Keyframes past a shortened clip's end no longer mean anything. */
function dropKeyframesAfter(clip: ClipItem): void {
  const length = itemFrames(clip);
  clip.keyframes = Object.fromEntries(
    Object.entries(clip.keyframes)
      .map(([prop, points]) => [prop, (points ?? []).filter((p) => p.f <= length)] as const)
      .filter(([, points]) => points.length),
  );
}

function splitKeyframes(keyframes: ClipItem['keyframes'], offset: number): [ClipItem['keyframes'], ClipItem['keyframes']] {
  const left: ClipItem['keyframes'] = {};
  const right: ClipItem['keyframes'] = {};
  for (const [prop, points] of Object.entries(keyframes) as Array<[KeyframeProp, Keyframe[]]>) {
    const before = points.filter((p) => p.f < offset);
    const after = points.filter((p) => p.f >= offset).map((p) => ({ ...p, f: p.f - offset }));
    if (before.length) left[prop] = before;
    if (after.length) right[prop] = after;
  }
  return [left, right];
}

function checkRule(field: string, value: unknown, rule: Rule): void {
  const bad = (why: string) => new TimelineError('BAD_PATCH', `That change doesn't fit: ${field} ${why}.`);
  if (rule.kind === 'bool') {
    if (typeof value !== 'boolean') throw bad('must be true or false');
    return;
  }
  if (rule.kind === 'object') return;
  const size = rule.kind === 'text' ? (typeof value === 'string' ? value.length : NaN) : (value as number);
  if (typeof size !== 'number' || Number.isNaN(size)) throw bad('has the wrong type');
  if (rule.kind === 'int' && !Number.isInteger(size)) throw bad('must be a whole number');
  if (rule.min !== undefined && size < rule.min) throw bad(`must be at least ${rule.min}`);
  if (rule.max !== undefined && size > rule.max) throw bad(`must be at most ${rule.max}`);
  if (rule.above !== undefined && size <= rule.above) throw bad(`must be more than ${rule.above}`);
}

const APPLY: { [K in TimelineOp['op']]: Applier<K> } = {
  add_track: (doc, op) => {
    doc.tracks.push({ id: op.id, kind: op.kind, items: [], muted: false });
  },
  add_item: (doc, op) => {
    findTrack(doc, op.track).items.push(normaliseItem(structuredClone(op.item)));
  },
  remove_item: (doc, op) => {
    const [track, item] = findItem(doc, op.item);
    track.items.splice(track.items.indexOf(item), 1);
    if (!op.ripple) return;
    const end = itemEnd(item);
    const frames = itemFrames(item);
    for (const later of track.items) if (later.at >= end) later.at -= frames;
  },
  move_item: (doc, op) => {
    const [track, item] = findItem(doc, op.item);
    item.at = op.at;
    if (op.track != null && op.track !== track.id) {
      const target = findTrack(doc, op.track);
      track.items.splice(track.items.indexOf(item), 1);
      target.items.push(item);
    }
  },
  trim_item: (doc, op) => {
    const clip = asClip(doc, op.item);
    if (op.src_in != null) clip.src_in = op.src_in;
    if (op.src_out != null) clip.src_out = op.src_out;
    dropKeyframesAfter(clip);
  },
  split_item: (doc, op) => {
    const clip = asClip(doc, op.item);
    const offset = op.at - clip.at;
    if (!(offset > 0 && offset < itemFrames(clip))) throw new TimelineError('OUT_OF_RANGE', `Frame ${op.at} is not inside ${clip.id}.`);
    const cut = clip.src_in + toFrames(offset * clip.speed);
    const [left, right] = splitKeyframes(clip.keyframes, offset);
    const piece: ClipItem = { ...structuredClone(clip), id: op.new_id, at: op.at, src_in: cut, transition_in: null, keyframes: right };
    clip.src_out = cut;
    clip.keyframes = left;
    findItem(doc, clip.id)[0].items.push(piece);
  },
  update_item: (doc, op) => {
    const [track, item] = findItem(doc, op.item);
    const rules = PATCH_RULES[item.type];
    const updated = structuredClone(item) as Item & Record<string, unknown>;
    for (const [field, value] of Object.entries(op.patch)) {
      if (value == null) continue;
      const rule = rules[field as keyof ItemPatch];
      if (!rule) throw new TimelineError('BAD_PATCH', `A ${item.type} has no ${field}.`);
      checkRule(field, value, rule);
      if (field === 'transform') {
        const merged = { ...(updated as { transform: Transform }).transform, ...(value as Partial<Transform>) };
        for (const key of Object.keys(TRANSFORM_RULES) as Array<keyof Transform>) checkRule(`transform.${key}`, merged[key], TRANSFORM_RULES[key]);
        updated.transform = merged;
      } else {
        updated[field] = structuredClone(value);
      }
    }
    if (updated.type === 'clip') dropKeyframesAfter(updated);
    track.items[track.items.indexOf(item)] = normaliseItem(updated);
  },
  replace_asset: (doc, op) => {
    const clip = asClip(doc, op.item);
    const length = clip.src_out - clip.src_in;
    clip.asset = op.asset;
    clip.src_in = 0;
    clip.src_out = length;
  },
  add_asset: (doc, op) => {
    if (op.asset.id in doc.assets) throw new TimelineError('DUPLICATE_ID', `The project already has an asset ${op.asset.id}.`);
    doc.assets[op.asset.id] = normaliseAsset(structuredClone(op.asset));
  },
  set_captions: (doc, op) => {
    const set: Partial<Captions> = {};
    if (op.enabled != null) set.enabled = op.enabled;
    if (op.style != null) set.style = op.style;
    if (op.language != null) set.language = op.language;
    if (op.follow != null) set.follow = op.follow;
    if (!doc.captions) {
      if (!set.follow) throw new TimelineError('UNKNOWN_TRACK', 'Say which track the captions follow.');
      doc.captions = { enabled: true, style: DEFAULT_CAPTION_STYLE, language: 'en', ...set } as Captions;
    } else {
      doc.captions = { ...doc.captions, ...set };
    }
  },
  set_project: (doc, op) => {
    if (op.look != null) doc.look = op.look;
    if (op.width != null) doc.width = op.width;
    if (op.height != null) doc.height = op.height;
  },
  add_marker: (doc, op) => {
    doc.markers = [...doc.markers.filter((m) => m.f !== op.marker.f), { ...op.marker }].sort((a, b) => a.f - b.f);
  },
  remove_marker: (doc, op) => {
    doc.markers = doc.markers.filter((m) => m.f !== op.f);
  },
};
