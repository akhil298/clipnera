/**
 * Two media elements per track, swapped at cuts: the visible one plays the
 * current item while the hidden one is loaded and seeked to the next, so a cut
 * shows no black frame (frontend.md §5.4). Works against a minimal element
 * interface, so tests drive it with fakes.
 */

/** The parts of HTMLMediaElement (and HTMLVideoElement) the pool touches. */
export interface MediaElementLike {
  src: string;
  currentTime: number;
  playbackRate: number;
  muted: boolean;
  volume: number;
  readonly paused: boolean;
  readonly readyState: number;
  play(): Promise<void> | void;
  pause(): void;
  removeAttribute(name: string): void;
  load(): void;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
  requestVideoFrameCallback?: (callback: () => void) => number;
}

/** What a track should be doing now. */
export interface PlayTarget {
  /** Item id; the same id means the same piece of media. */
  key: string;
  url: string;
  /** Source seconds. */
  sourceTime: number;
  /** Element rate: clock rate × clip speed. */
  rate: number;
  /** Linear gain 0..2 (elements cap at 1). */
  gain: number;
}

export interface TrackPoolOptions<E extends MediaElementLike> {
  create: () => E;
  /** Show or hide an element (the engine sets visibility; audio ignores it). */
  setVisible: (element: E, visible: boolean) => void;
  /** An element failed while holding `url` for item `key`. */
  onError: (key: string, url: string) => void;
  /** An element started playing `key`, so its URL works. */
  onPlaying?: (key: string) => void;
  muted?: boolean;
}

interface Slot<E> {
  element: E;
  key: string | null;
  url: string | null;
  listeners: Array<[string, () => void]>;
}

/** Re-seek a playing element only past this drift; seeking every frame stutters. */
export const PLAYING_DRIFT = 0.25;
/** Paused, the element must show the exact frame. */
export const PAUSED_DRIFT = 0.01;
/** HAVE_FUTURE_DATA: enough to keep playing. */
const READY_TO_PLAY = 3;

export class TrackPool<E extends MediaElementLike> {
  private readonly slots: [Slot<E>, Slot<E>];
  private active = 0;
  private playing = false;
  private muted: boolean;
  private target: PlayTarget | null = null;
  private readonly options: TrackPoolOptions<E>;

  constructor(options: TrackPoolOptions<E>) {
    this.options = options;
    this.muted = options.muted ?? false;
    this.slots = [this.slot(), this.slot()];
    this.slots.forEach((s) => options.setVisible(s.element, false));
  }

  get elements(): readonly E[] {
    return this.slots.map((s) => s.element);
  }

  /** The element showing now (for drawing a frame, e.g. a thumbnail or export). */
  get current(): E | null {
    return this.target ? this.slots[this.active].element : null;
  }

  /** Make the track show `target` (null: nothing at this time). */
  show(target: PlayTarget | null, playing: boolean): void {
    this.target = target;
    this.playing = playing;
    if (!target) {
      for (const s of this.slots) {
        s.element.pause();
        this.options.setVisible(s.element, false);
      }
      return;
    }
    const standby = this.slots[1 - this.active];
    const swapping = standby.key === target.key && this.slots[this.active].key !== target.key;
    if (swapping) this.active = 1 - this.active;
    const slot = this.slots[this.active];
    this.load(slot, target);
    this.drive(slot, target, playing);
    this.reveal(slot, swapping && playing);
  }

  /** Load the next item into the hidden element, seeked to where it will start. */
  preload(next: Omit<PlayTarget, 'rate' | 'gain'> | null): void {
    if (!next || this.slots[this.active].key === next.key) return;
    const standby = this.slots[1 - this.active];
    if (standby.key === next.key && standby.url === next.url) return;
    standby.element.pause();
    this.load(standby, next);
  }

  /** Playing, but the visible element can't keep up. */
  get stalled(): boolean {
    return this.playing && this.target !== null && this.slots[this.active].element.readyState < READY_TO_PLAY;
  }

  /** A fresh URL for `key` (after a refresh): reload it where it was, keep playing. */
  replaceUrl(key: string, url: string): void {
    for (const slot of this.slots) {
      if (slot.key !== key || slot.url === url) continue;
      const at = slot.element.currentTime;
      slot.url = url;
      slot.element.src = url;
      slot.element.currentTime = at;
      if (slot === this.slots[this.active] && this.playing) void Promise.resolve(slot.element.play()).catch(() => undefined);
    }
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    for (const s of this.slots) s.element.muted = muted;
  }

  destroy(): void {
    for (const slot of this.slots) {
      slot.listeners.forEach(([type, fn]) => slot.element.removeEventListener(type, fn));
      slot.element.pause();
      slot.element.removeAttribute('src');
      slot.element.load();
    }
  }

  private slot(): Slot<E> {
    const element = this.options.create();
    element.muted = this.muted;
    const slot: Slot<E> = { element, key: null, url: null, listeners: [] };
    const onError = () => slot.key && slot.url && this.options.onError(slot.key, slot.url);
    const onPlaying = () => slot.key && this.options.onPlaying?.(slot.key);
    slot.listeners = [['error', onError], ['playing', onPlaying]];
    slot.listeners.forEach(([type, fn]) => element.addEventListener(type, fn));
    return slot;
  }

  private load(slot: Slot<E>, target: Pick<PlayTarget, 'key' | 'url' | 'sourceTime'>): void {
    if (slot.url !== target.url) {
      slot.element.src = target.url;
      slot.url = target.url;
      slot.element.currentTime = target.sourceTime;
    } else if (slot.key !== target.key) {
      slot.element.currentTime = target.sourceTime;
    }
    slot.key = target.key;
  }

  private drive(slot: Slot<E>, target: PlayTarget, playing: boolean): void {
    const el = slot.element;
    if (el.playbackRate !== target.rate) el.playbackRate = target.rate;
    el.volume = Math.min(1, Math.max(0, target.gain));
    el.muted = this.muted;
    if (Math.abs(el.currentTime - target.sourceTime) > (playing ? PLAYING_DRIFT : PAUSED_DRIFT)) el.currentTime = target.sourceTime;
    if (playing && el.paused) void Promise.resolve(el.play()).catch(() => undefined);
    if (!playing && !el.paused) el.pause();
  }

  /** Show the active element; on a playing swap, hide the old one once the new one has painted a frame. */
  private reveal(slot: Slot<E>, swapping: boolean): void {
    const other = this.slots[1 - this.active];
    this.options.setVisible(slot.element, true);
    const hideOther = () => {
      if (this.slots[this.active] !== slot) return;
      other.element.pause();
      this.options.setVisible(other.element, false);
    };
    if (swapping && slot.element.requestVideoFrameCallback) slot.element.requestVideoFrameCallback(hideOther);
    else hideOther();
  }
}
