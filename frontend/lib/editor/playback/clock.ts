/**
 * The editor's playback clock. It lives outside React: the rAF loop advances a
 * mutable time, and subscribers (the preview engine, the playhead, a throttled
 * timecode) read it without re-rendering the editor 60 times a second
 * (frontend.md §5.3). Time is in timeline seconds; frames come from `fps`.
 *
 * Only `import type` here, so `node --test` loads it directly.
 */

export interface Range {
  /** Seconds, inclusive. */
  start: number;
  /** Seconds, exclusive. */
  end: number;
}

export interface ClockState {
  time: number;
  /** Whole frame at `time`. */
  frame: number;
  playing: boolean;
  /** Playing, but holding still until the media catches up. */
  buffering: boolean;
  rate: number;
  duration: number;
  fps: number;
  loop: Range | null;
  ended: boolean;
}

export type ClockEvent =
  | { type: 'play' }
  | { type: 'pause'; reason: 'user' | 'ended' | 'hidden' }
  | { type: 'seek'; from: number; to: number }
  | { type: 'loop'; to: number }
  | { type: 'ended' }
  | { type: 'rate'; rate: number }
  | { type: 'buffering'; buffering: boolean };

/** The animation-frame source, injectable so tests drive time by hand. */
export interface Scheduler {
  now(): number;
  request(callback: (now: number) => void): number;
  cancel(handle: number): void;
}

export interface ClockOptions {
  fps: number;
  duration: number;
  scheduler?: Scheduler;
  /** Resume when the tab comes back if hiding it paused playback. Default true. */
  resumeOnVisible?: boolean;
}

export const MIN_RATE = 0.25;
export const MAX_RATE = 4;
/** Float slack so 1/fps steps land on the frame they mean. */
const FRAME_EPSILON = 1e-6;

type Listener = (state: ClockState) => void;
interface Subscription {
  listener: Listener;
  throttleMs: number;
  last: number;
}

export const frameAt = (time: number, fps: number): number => Math.floor(time * fps + FRAME_EPSILON);
export const timeOfFrame = (frame: number, fps: number): number => frame / fps;
export const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

/** Where playback lands after `time` if it ran into a skipped range (cut words). */
export function skipForward(time: number, skips: readonly Range[]): number {
  let t = time;
  for (const range of skips) if (t >= range.start && t < range.end) t = range.end;
  return t;
}

/** rAF while visible; a 60 Hz timer while hidden (only reached when exporting, since hiding pauses otherwise). */
export function browserScheduler(doc: Pick<Document, 'hidden'> | null = typeof document === 'undefined' ? null : document): Scheduler {
  const timers = new Map<number, 'raf' | 'timer'>();
  return {
    now: () => performance.now(),
    request(callback) {
      if (doc?.hidden || typeof requestAnimationFrame === 'undefined') {
        const handle = setTimeout(() => callback(performance.now()), 16) as unknown as number;
        timers.set(handle, 'timer');
        return handle;
      }
      const handle = requestAnimationFrame(callback);
      timers.set(handle, 'raf');
      return handle;
    },
    cancel(handle) {
      if (timers.get(handle) === 'timer') clearTimeout(handle);
      else cancelAnimationFrame(handle);
      timers.delete(handle);
    },
  };
}

export class PlaybackClock {
  private readonly scheduler: Scheduler;
  private readonly resumeOnVisible: boolean;
  private readonly subs = new Set<Subscription>();
  private readonly eventListeners = new Set<(event: ClockEvent) => void>();
  private snapshot: ClockState;
  /** Wall time and clock time when playback last (re)started, so ticks never accumulate drift. */
  private anchor = { now: 0, time: 0 };
  private handle: number | null = null;
  private skips: readonly Range[] = [];
  private hidden = false;
  private exporting = false;
  private pausedByHiding = false;

  constructor(options: ClockOptions) {
    this.scheduler = options.scheduler ?? browserScheduler();
    this.resumeOnVisible = options.resumeOnVisible ?? true;
    this.snapshot = {
      time: 0, frame: 0, playing: false, buffering: false, rate: 1,
      duration: Math.max(0, options.duration), fps: options.fps, loop: null, ended: false,
    };
  }

  /** Stable between changes, so `useSyncExternalStore` can read it directly. */
  getState = (): ClockState => this.snapshot;

  get time(): number {
    return this.snapshot.time;
  }

  /**
   * Called on every change. `throttleMs` limits time-only updates (ticks); seeks,
   * play, pause and rate changes always arrive at once. Returns the unsubscribe.
   */
  subscribe = (listener: Listener, throttleMs = 0): (() => void) => {
    const sub: Subscription = { listener, throttleMs, last: -Infinity };
    this.subs.add(sub);
    return () => this.subs.delete(sub);
  };

  on(listener: (event: ClockEvent) => void): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  play(): void {
    if (this.snapshot.playing || this.snapshot.duration <= 0) return;
    const { time, duration, loop } = this.snapshot;
    const restart = loop ? time < loop.start || time >= loop.end : time >= duration - 1 / this.snapshot.fps / 2;
    const from = restart ? (loop?.start ?? 0) : time;
    this.pausedByHiding = false;
    this.set({ playing: true, ended: false, time: from }, 'change');
    this.emit({ type: 'play' });
    if (this.hidden && !this.exporting) {
      this.pause('hidden');
      return;
    }
    this.start();
  }

  pause(reason: 'user' | 'ended' | 'hidden' = 'user'): void {
    if (!this.snapshot.playing) return;
    this.stop();
    this.pausedByHiding = reason === 'hidden';
    this.set({ playing: false, buffering: false }, 'change');
    this.emit({ type: 'pause', reason });
  }

  toggle(): void {
    if (this.snapshot.playing) this.pause();
    else this.play();
  }

  seek(time: number): void {
    const from = this.snapshot.time;
    const to = clamp(time, 0, this.snapshot.duration);
    this.reanchor(to);
    this.set({ time: to, ended: false }, 'change');
    this.emit({ type: 'seek', from, to });
  }

  seekFrame(frame: number): void {
    this.seek(timeOfFrame(frame, this.snapshot.fps));
  }

  /** Pause and move by whole frames (←/→ in the editor). */
  step(frames: number): void {
    this.pause();
    const last = Math.max(0, Math.ceil(this.snapshot.duration * this.snapshot.fps - FRAME_EPSILON) - 1);
    this.seekFrame(clamp(this.snapshot.frame + frames, 0, last));
  }

  setRate(rate: number): void {
    const next = clamp(rate, MIN_RATE, MAX_RATE);
    if (next === this.snapshot.rate) return;
    this.reanchor(this.snapshot.time);
    this.set({ rate: next }, 'change');
    this.emit({ type: 'rate', rate: next });
  }

  /** Loop `range` (seconds) while playing; null plays to the end. */
  setLoop(range: Range | null): void {
    const loop = range && range.end > range.start
      ? { start: clamp(range.start, 0, this.snapshot.duration), end: clamp(range.end, 0, this.snapshot.duration) }
      : null;
    this.set({ loop }, 'change');
  }

  /** A new edit changed the length; the playhead stays put unless it is now past the end. */
  setDuration(duration: number): void {
    const next = Math.max(0, duration);
    const time = Math.min(this.snapshot.time, next);
    if (time !== this.snapshot.time) this.reanchor(time);
    this.set({ duration: next, time }, 'change');
  }

  setFps(fps: number): void {
    this.set({ fps }, 'change');
  }

  /** Ranges playback jumps over, e.g. cut words in clip mode. */
  setSkips(skips: readonly Range[]): void {
    this.skips = [...skips].sort((a, b) => a.start - b.start);
  }

  /** The media is waiting for data: hold the clock still without leaving play. */
  setBuffering(buffering: boolean): void {
    if (buffering === this.snapshot.buffering) return;
    this.reanchor(this.snapshot.time);
    this.set({ buffering }, 'change');
    this.emit({ type: 'buffering', buffering });
  }

  /** The tab was hidden or shown. Hiding pauses, unless an export is drawing frames. */
  setHidden(hidden: boolean): void {
    this.hidden = hidden;
    if (hidden && !this.exporting) this.pause('hidden');
    else if (!hidden && this.pausedByHiding && this.resumeOnVisible) this.play();
  }

  setExporting(exporting: boolean): void {
    this.exporting = exporting;
    if (!exporting && this.hidden) this.pause('hidden');
  }

  destroy(): void {
    this.stop();
    this.subs.clear();
    this.eventListeners.clear();
  }

  private start(): void {
    this.anchor = { now: this.scheduler.now(), time: this.snapshot.time };
    this.handle = this.scheduler.request(this.tick);
  }

  private stop(): void {
    if (this.handle !== null) this.scheduler.cancel(this.handle);
    this.handle = null;
  }

  private reanchor(time: number): void {
    this.anchor = { now: this.scheduler.now(), time };
  }

  private tick = (now: number): void => {
    this.handle = null;
    if (!this.snapshot.playing) return;
    const { rate, duration, loop, buffering } = this.snapshot;
    if (buffering) {
      this.anchor = { now, time: this.snapshot.time };
      this.handle = this.scheduler.request(this.tick);
      return;
    }
    const elapsed = this.anchor.time + ((now - this.anchor.now) / 1000) * rate;
    let time = skipForward(elapsed, this.skips);
    if (time !== elapsed) this.anchor = { now, time };
    if (loop && time >= loop.end) {
      time = loop.start;
      this.anchor = { now, time };
      this.set({ time }, 'change');
      this.emit({ type: 'loop', to: time });
    } else if (time >= duration) {
      this.stop();
      this.set({ time: duration, playing: false, ended: true }, 'change');
      this.emit({ type: 'pause', reason: 'ended' });
      this.emit({ type: 'ended' });
      return;
    } else {
      this.set({ time }, 'tick');
    }
    this.handle = this.scheduler.request(this.tick);
  };

  private set(patch: Partial<ClockState>, kind: 'tick' | 'change'): void {
    const next = { ...this.snapshot, ...patch };
    next.frame = frameAt(next.time, next.fps);
    this.snapshot = next;
    const now = this.scheduler.now();
    for (const sub of this.subs) {
      if (kind === 'tick' && now - sub.last < sub.throttleMs) continue;
      sub.last = now;
      sub.listener(next);
    }
  }

  private emit(event: ClockEvent): void {
    for (const listener of this.eventListeners) listener(event);
  }
}
