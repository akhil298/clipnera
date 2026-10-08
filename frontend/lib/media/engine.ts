/**
 * PreviewEngine: plays a Timeline v1 in the browser from proxies, with no
 * render. Extracted from the core of the legacy ReelPreviewPlayer (wall clock
 * as master, media elements slaved to it, synced on item boundaries) and the
 * clip studio player (rate, mute, skipped ranges), generalised to any number
 * of tracks with A/B element pairs for gapless cuts (frontend.md §5.4).
 *
 * UI-free: it creates and drives media elements inside a container the
 * preview zone hands it; overlays (captions, text, B-roll chrome) are drawn by
 * the caller from `overlays()`.
 */
import { PlaybackClock, type ClockEvent, type Range, type Scheduler } from '../editor/playback/clock';
import { duration as timelineFrames, type SfxItem, type Timeline, type Track } from '../editor/timeline';
import { placeSource } from './fit';
import { audibleAt, cuesBetween, dbToGain, evaluateOverlays, itemAfter, type ActiveClip, type CaptionWord, type OverlayFrame } from './overlays';
import { TrackPool, type MediaElementLike } from './pool';
import { MediaUrls, type MediaRef, type UrlResolver } from './urls';

export type EngineEvent =
  | ClockEvent
  /** A sound effect starts now; `url` is null when the resolver had none (the caller may synthesise it). */
  | { type: 'cue'; sfx: SfxItem; url: string | null }
  /** A link failed and a fresh one was fetched; playback carried on. */
  | { type: 'url-refreshed'; ref: MediaRef }
  /** A source could not be played even with a fresh link: "This video could not play. Your edit is safe." */
  | { type: 'media-error'; ref: MediaRef }
  | { type: 'reduced-motion'; reduced: boolean };

export interface PreviewEngineOptions {
  timeline: Timeline;
  /** Gives a signed URL for an asset (proxy preferred), a music track or a sound effect. */
  resolveUrl: UrlResolver;
  /** Caption words in timeline seconds, for `overlays()`. */
  words?: readonly CaptionWord[];
  scheduler?: Scheduler;
  /** Element factory; defaults to `document.createElement`. */
  createElement?: (kind: 'video' | 'audio' | 'img') => HTMLElement;
  /** Visibility source (background tab); defaults to `document`. */
  document?: Document | null;
  /** Reduced-motion source; defaults to `window.matchMedia`. */
  matchMedia?: ((query: string) => MediaQueryList) | null;
}

/** Load the next clip into the standby element this far ahead of its cut. */
export const PRELOAD_SECONDS = 0.5;

interface VisualLayer {
  track: Track;
  pool: TrackPool<HTMLVideoElement & MediaElementLike>;
  image: HTMLImageElement;
}

interface AudioLayer {
  track: Track;
  pool: TrackPool<HTMLMediaElement & MediaElementLike>;
}

const isVisual = (track: Track) => track.kind === 'video' || track.kind === 'overlay';
const trackSignature = (timeline: Timeline) => timeline.tracks.map((t) => `${t.id}:${t.kind}`).join('|');

export class PreviewEngine {
  readonly clock: PlaybackClock;
  readonly urls: MediaUrls;
  private timeline: Timeline;
  private words: readonly CaptionWord[];
  private reduced = false;
  private muted = false;
  private container: HTMLElement | null = null;
  private visual: VisualLayer[] = [];
  private audio: AudioLayer[] = [];
  private signature = '';
  private lastTime = 0;
  private syncing = false;
  private readonly listeners = new Set<(event: EngineEvent) => void>();
  private readonly cleanups: Array<() => void> = [];
  private readonly create: NonNullable<PreviewEngineOptions['createElement']>;

  constructor(options: PreviewEngineOptions) {
    this.timeline = options.timeline;
    this.words = options.words ?? [];
    this.create = options.createElement ?? ((kind) => document.createElement(kind));
    this.urls = new MediaUrls(options.resolveUrl);
    this.clock = new PlaybackClock({ fps: this.timeline.fps, duration: this.seconds(), scheduler: options.scheduler });
    this.cleanups.push(this.clock.subscribe(this.sync), this.clock.on((event) => this.emit(event)));
    this.watchEnvironment(options);
    this.rebuild();
  }

  // --- Transport (thin pass-throughs, so callers need only the engine) -----------

  play = (): void => this.clock.play();
  pause = (): void => this.clock.pause();
  toggle = (): void => this.clock.toggle();
  seek = (seconds: number): void => this.clock.seek(seconds);
  seekFrame = (frame: number): void => this.clock.seekFrame(frame);
  step = (frames: number): void => this.clock.step(frames);
  setRate = (rate: number): void => this.clock.setRate(rate);
  setLoop = (range: Range | null): void => this.clock.setLoop(range);
  setSkips = (ranges: readonly Range[]): void => this.clock.setSkips(ranges);
  /** Keep the clock running in a hidden tab while an export draws frames. */
  setExporting = (exporting: boolean): void => this.clock.setExporting(exporting);

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.audio.forEach((layer) => layer.pool.setMuted(muted));
  }

  get reducedMotion(): boolean {
    return this.reduced;
  }

  on(listener: (event: EngineEvent) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  // --- Document -----------------------------------------------------------------

  /** A new edit: the playhead stays where it is (01 §6), clamped to the new length. */
  setTimeline(timeline: Timeline): void {
    this.timeline = timeline;
    this.clock.setFps(timeline.fps);
    this.clock.setDuration(this.seconds());
    this.rebuild();
  }

  setWords(words: readonly CaptionWord[]): void {
    this.words = words;
  }

  /** What to draw over the video at `time` (default: now). */
  overlays(time = this.clock.time, wordsPerLine?: number): OverlayFrame {
    return evaluateOverlays(this.timeline, time, { words: this.words, wordsPerLine, reducedMotion: this.reduced });
  }

  // --- DOM ------------------------------------------------------------------------

  /** Put the picture layers in `container` (positioned, overflow hidden), bottom track first. */
  mount(container: HTMLElement): void {
    this.container = container;
    this.attachLayers();
    this.sync();
  }

  unmount(): void {
    for (const layer of this.visual) [...layer.pool.elements, layer.image].forEach((el) => el.remove());
    this.container = null;
  }

  destroy(): void {
    this.unmount();
    this.visual.forEach((l) => l.pool.destroy());
    this.audio.forEach((l) => l.pool.destroy());
    this.cleanups.forEach((fn) => fn());
    this.clock.destroy();
    this.listeners.clear();
  }

  // --- Internals --------------------------------------------------------------------

  private seconds(): number {
    return timelineFrames(this.timeline) / this.timeline.fps;
  }

  private emit(event: EngineEvent): void {
    this.listeners.forEach((listener) => listener(event));
  }

  private watchEnvironment(options: PreviewEngineOptions): void {
    const doc = options.document === undefined ? (typeof document === 'undefined' ? null : document) : options.document;
    if (doc) {
      const onVisibility = () => this.clock.setHidden(doc.hidden);
      doc.addEventListener('visibilitychange', onVisibility);
      this.cleanups.push(() => doc.removeEventListener('visibilitychange', onVisibility));
    }
    const match = options.matchMedia === undefined ? (typeof window === 'undefined' ? null : window.matchMedia?.bind(window)) : options.matchMedia;
    const query = match?.('(prefers-reduced-motion: reduce)');
    if (query) {
      this.reduced = query.matches;
      const onChange = () => {
        this.reduced = query.matches;
        this.emit({ type: 'reduced-motion', reduced: this.reduced });
      };
      query.addEventListener('change', onChange);
      this.cleanups.push(() => query.removeEventListener('change', onChange));
    }
  }

  /** Make element pools match the tracks (only when tracks were added, removed or retyped) and warm the URLs. */
  private rebuild(): void {
    const signature = trackSignature(this.timeline);
    if (signature !== this.signature) {
      const container = this.container;
      this.unmount();
      this.visual.forEach((l) => l.pool.destroy());
      this.audio.forEach((l) => l.pool.destroy());
      this.visual = this.timeline.tracks.filter(isVisual).map((track) => this.visualLayer(track));
      this.audio = this.timeline.tracks.filter((t) => t.kind === 'audio').map((track) => this.audioLayer(track));
      this.signature = signature;
      if (container) this.mount(container);
    } else {
      const byId = new Map(this.timeline.tracks.map((t) => [t.id, t]));
      [...this.visual, ...this.audio].forEach((layer) => (layer.track = byId.get(layer.track.id) ?? layer.track));
    }
    void this.urls.prime(this.timeline.tracks.flatMap((t) => t.items.flatMap((i) => {
      const ref = this.refFor(i.id);
      return ref ? [ref] : [];
    }))).then(() => this.sync());
    this.sync();
  }

  private visualLayer(track: Track): VisualLayer {
    const pool = new TrackPool<HTMLVideoElement & MediaElementLike>({
      create: () => {
        const video = this.create('video') as HTMLVideoElement;
        video.muted = true;
        video.playsInline = true;
        video.preload = 'auto';
        video.setAttribute('aria-hidden', 'true');
        Object.assign(video.style, { position: 'absolute', objectFit: 'fill', pointerEvents: 'none' });
        return video;
      },
      setVisible: (el, visible) => (el.style.visibility = visible ? 'visible' : 'hidden'),
      onError: (key, url) => this.recover(key, url),
      onPlaying: (key) => this.confirm(key),
      muted: true,
    });
    const image = this.create('img') as HTMLImageElement;
    image.alt = '';
    Object.assign(image.style, { position: 'absolute', visibility: 'hidden', pointerEvents: 'none' });
    image.addEventListener('error', () => {
      const key = image.dataset.key;
      if (key) this.recover(key, image.src);
    });
    return { track, pool, image };
  }

  private audioLayer(track: Track): AudioLayer {
    const pool = new TrackPool<HTMLMediaElement & MediaElementLike>({
      create: () => {
        const el = this.create('audio') as HTMLAudioElement;
        el.preload = 'auto';
        return el;
      },
      setVisible: () => undefined,
      onError: (key, url) => this.recover(key, url),
      onPlaying: (key) => this.confirm(key),
      muted: this.muted,
    });
    return { track, pool };
  }

  private attachLayers(): void {
    if (!this.container) return;
    for (const layer of this.visual) [...layer.pool.elements, layer.image].forEach((el) => this.container!.appendChild(el));
  }

  /** The media an item plays, by item id. */
  private refFor(key: string): MediaRef | null {
    for (const track of this.timeline.tracks) {
      const item = track.items.find((i) => i.id === key);
      if (!item) continue;
      if (item.type === 'clip') {
        const asset = this.timeline.assets[item.asset];
        return asset ? { kind: 'asset', asset } : null;
      }
      if (item.type === 'music') return { kind: 'music', track: item.track };
      if (item.type === 'sfx') return { kind: 'sfx', name: item.name };
      return null;
    }
    return null;
  }

  private urlFor(key: string): string | null {
    const ref = this.refFor(key);
    return ref ? this.urls.peek(ref) : null;
  }

  private confirm(key: string): void {
    const ref = this.refFor(key);
    if (ref) this.urls.confirm(ref);
  }

  /** A failed element: fetch a fresh link and reload in place; give up after repeated failures. */
  private recover(key: string, failedUrl: string): void {
    const ref = this.refFor(key);
    if (!ref) return;
    this.urls.refresh(ref, failedUrl).then((url) => {
      [...this.visual, ...this.audio].forEach((layer) => layer.pool.replaceUrl(key, url));
      this.visual.filter((l) => l.image.dataset.key === key).forEach((l) => (l.image.src = url));
      this.emit({ type: 'url-refreshed', ref });
    }).catch(() => {
      this.clock.pause();
      this.emit({ type: 'media-error', ref });
    });
  }

  /** Bring every element in line with the clock. Runs on every clock change. */
  private sync = (): void => {
    if (this.syncing) return;
    this.syncing = true;
    try {
      const { time, playing, rate } = this.clock.getState();
      const fps = this.timeline.fps;
      const frame = Math.floor(time * fps + 1e-6);
      const lookahead = Math.round(PRELOAD_SECONDS * fps);
      const layers = new Map(evaluateOverlays(this.timeline, time, { reducedMotion: this.reduced }).layers.map((c) => [c.track.id, c]));
      let waiting = false;

      for (const layer of this.visual) {
        const clip = layers.get(layer.track.id) ?? null;
        waiting = this.syncVisual(layer, clip, playing, rate) || waiting;
        const next = itemAfter(layer.track.items, frame);
        const nextUrl = next ? this.urlFor(next.id) : null;
        if (next?.type === 'clip' && nextUrl && next.at - frame <= lookahead && this.timeline.assets[next.asset]?.kind === 'video') {
          layer.pool.preload({ key: next.id, url: nextUrl, sourceTime: next.src_in / fps });
        }
      }

      const audible = new Map(audibleAt(this.timeline, time).map((a) => [a.track.id, a]));
      for (const layer of this.audio) {
        const sound = audible.get(layer.track.id);
        const url = sound ? this.urlFor(sound.item.id) : null;
        if (sound && !url) waiting = true;
        layer.pool.show(sound && url ? {
          key: sound.item.id, url, sourceTime: sound.sourceTime, gain: sound.gain,
          rate: rate * (sound.item.type === 'clip' ? sound.item.speed : 1),
        } : null, playing);
        const next = itemAfter(layer.track.items, frame);
        const nextUrl = next && next.type !== 'sfx' ? this.urlFor(next.id) : null;
        if (next && nextUrl && next.at - frame <= lookahead) {
          layer.pool.preload({ key: next.id, url: nextUrl, sourceTime: next.type === 'clip' ? next.src_in / fps : next.type === 'music' ? next.offset / fps : 0 });
        }
      }

      if (playing && time > this.lastTime && time - this.lastTime < 1) {
        for (const sfx of cuesBetween(this.timeline, this.lastTime, time)) this.fire(sfx);
      }
      this.lastTime = time;
      const stalled = [...this.visual, ...this.audio].some((l) => l.pool.stalled);
      this.clock.setBuffering(playing && (waiting || stalled));
    } finally {
      this.syncing = false;
    }
  };

  /** Play a sound effect once (unless muted) and tell listeners, who may synthesise it when there is no file. */
  private fire(sfx: SfxItem): void {
    const url = this.muted ? null : this.urlFor(sfx.id);
    if (url) {
      const el = this.create('audio') as HTMLAudioElement;
      el.src = url;
      el.volume = Math.min(1, dbToGain(sfx.gain_db));
      void el.play().catch(() => undefined);
    }
    this.emit({ type: 'cue', sfx, url });
  }

  /** Show `clip` on its layer; returns true while its URL is still loading. */
  private syncVisual(layer: VisualLayer, clip: ActiveClip | null, playing: boolean, rate: number): boolean {
    const url = clip ? this.urlFor(clip.item.id) : null;
    const isImage = clip?.asset.kind === 'image';
    layer.pool.show(clip && url && !isImage
      ? { key: clip.item.id, url, sourceTime: clip.sourceTime, rate: rate * clip.item.speed, gain: 0 }
      : null, playing);
    if (isImage && url) {
      if (layer.image.dataset.key !== clip.item.id || layer.image.getAttribute('src') !== url) {
        layer.image.dataset.key = clip.item.id;
        layer.image.src = url;
      }
    }
    layer.image.style.visibility = isImage && url ? 'visible' : 'hidden';
    const shown = isImage ? layer.image : layer.pool.current;
    if (clip && shown) this.place(shown, clip);
    return Boolean(clip && !url);
  }

  /** Position a layer's element as the renderer would frame it, with keyframes and the way in. */
  private place(el: HTMLElement, clip: ActiveClip): void {
    const frame = { width: this.timeline.width, height: this.timeline.height };
    const source = { width: clip.asset.width ?? frame.width, height: clip.asset.height ?? frame.height };
    const rect = placeSource(source, frame, clip.transform);
    const way = clip.transition;
    const p = way?.progress ?? 1;
    const motion = way?.type === 'slide_left' ? `translateX(${((1 - p) * 100).toFixed(2)}%) ` : way?.type === 'zoom' ? `scale(${(1.2 - 0.2 * p).toFixed(4)}) ` : '';
    Object.assign(el.style, {
      left: `${rect.x * 100}%`, top: `${rect.y * 100}%`, width: `${rect.width * 100}%`, height: `${rect.height * 100}%`,
      transform: `${motion}rotate(${clip.transform.rotation}deg)`,
      opacity: String(clip.opacity * (way && way.type !== 'slide_left' ? p : 1)),
    });
  }
}
