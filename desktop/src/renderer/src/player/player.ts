import type { SfxItem, Timeline } from '@timeline'
import { playbackUrl, type MediaItem } from '../../../shared/media'
import { createStore } from '../state/store'
import { AudioMix, mixPlan } from './audio'
import { framingAt, type Framing } from './framing'
import { segmentAt, segments, sourceTime, timelineSeconds, type Segment } from './sequence'
import { frameToTime, nextShuttle, rateOf, timeToFrame } from './time'

/** timeline: the edit, cut to cut · source: one media file from the library. */
export type ViewerMode = 'timeline' | 'source'

export interface PlayerState {
  mode: ViewerMode
  /** The file shown in source mode. */
  item: MediaItem | null
  time: number
  duration: number
  /** 0 paused, 1/2/4 forward, -1/-2/-4 reverse. */
  speed: number
  /** True when the playhead is between clips: the viewer shows black. */
  gap: boolean
  /** The timeline clip under the playhead. */
  clipId: string | null
  /** How that clip is framed (zoom, crop centre), as the export draws it; null shows the whole picture. */
  framing: Framing | null
}

const INITIAL: PlayerState = { mode: 'timeline', item: null, time: 0, duration: 0, speed: 0, gap: true, clipId: null, framing: null }
// Further apart than this and the footage is re-seeked to where the clock says it should be.
const DRIFT = 0.3

/** Asset id → a URL that plays it, or null when it can't be played yet. */
export type AssetResolver = (assetId: string) => string | null

/**
 * Drives the viewer. One clock moves the playhead in both modes; the media element follows
 * it: it gets the right file and moment for the clip under the playhead and is only
 * re-seeked when it drifts. Reverse shuttle moves the clock back. Seeks are queued, since
 * Chromium's decoder can hang when a seek starts before the last one finished.
 */
export class Player {
  readonly state = createStore<PlayerState>(INITIAL)
  private media: HTMLMediaElement | null = null
  private loop = 0
  private clockStart = 0
  private timeAtStart = 0
  private rangeEnd: number | null = null
  private pendingSeek: number | null = null
  private source = ''
  private timeline: Timeline | null = null
  private resolve: AssetResolver = () => null
  private mix: AudioMix | null = null
  private apiUrl = ''

  /** Where the viewer's music and sound effects play. */
  attachMix(container: HTMLElement | null): void {
    this.mix?.stop()
    this.mix = container ? new AudioMix(container) : null
    this.updateMix()
  }

  /** The backend serves the sound effects library; the AI's sounds name files under it. */
  setApiUrl(url: string): void {
    this.apiUrl = url.replace(/\/$/, '')
    this.updateMix()
  }

  private soundUrl = (item: SfxItem): string | null => {
    const url = typeof item.extra.url === 'string' ? item.extra.url : null
    if (!url) return null
    return /^https?:/.test(url) ? url : `${this.apiUrl}${url.startsWith('/') ? '' : '/'}${url}`
  }

  private updateMix(): void {
    if (this.mix && this.timeline) this.mix.update(mixPlan(this.timeline, this.resolve, this.soundUrl))
  }

  attach(media: HTMLMediaElement | null): void {
    this.media = media
    this.source = ''
    if (!media) return this.stopLoop()
    media.onseeked = () => {
      if (this.pendingSeek === null) return
      const time = this.pendingSeek
      this.pendingSeek = null
      media.currentTime = time
    }
    this.present(this.state.get().time)
  }

  get fps(): number {
    const { mode, item } = this.state.get()
    return mode === 'source' ? rateOf(item?.info?.fps) : rateOf(this.timeline?.fps)
  }

  /** Called whenever the project changes; keeps the playhead where it was. */
  /** Where the viewer plays an asset from (a proxy on this Mac, or the project's copy). */
  assetUrl(id: string): string | null {
    return this.resolve(id)
  }

  setTimeline(timeline: Timeline | null, resolve: AssetResolver): void {
    this.timeline = timeline
    this.resolve = resolve
    this.updateMix()
    if (this.state.get().mode !== 'timeline') return
    const duration = timeline ? timelineSeconds(timeline) : 0
    this.state.set({ duration, time: Math.min(this.state.get().time, duration) })
    if (this.state.get().speed === 0) this.present(this.state.get().time)
  }

  showTimeline(): void {
    this.halt()
    this.state.set({ mode: 'timeline', item: null, time: 0, duration: this.timeline ? timelineSeconds(this.timeline) : 0 })
    this.present(0)
  }

  open(item: MediaItem): void {
    if (item.status !== 'ready' && item.status !== 'uploading') throw new Error(`${item.name} isn't ready yet`)
    this.halt()
    this.state.set({ mode: 'source', item, time: 0, duration: item.info?.durationSeconds ?? 0 })
    this.present(0)
  }

  /** Leaves source mode when its file goes away. */
  close(): void {
    if (this.state.get().mode === 'source') this.showTimeline()
  }

  play(): void {
    this.shuttleTo(1)
  }

  pause(): void {
    this.halt()
    this.present(this.state.get().time)
  }

  toggle(): void {
    if (this.state.get().speed === 0) this.play()
    else this.pause()
  }

  seek(seconds: number): void {
    this.requireContent()
    const time = Math.min(Math.max(0, seconds), this.state.get().duration)
    this.timeAtStart = time
    this.clockStart = performance.now()
    this.state.set({ time })
    this.present(time)
  }

  step(frames: number): void {
    this.pause()
    this.seek(frameToTime(timeToFrame(this.state.get().time, this.fps) + frames, this.fps))
  }

  shuttle(direction: 1 | -1): void {
    this.shuttleTo(nextShuttle(this.state.get().speed, direction))
  }

  /** Plays from `from` and stops at `to` (seconds). */
  playRange(from: number, to: number): void {
    if (!(to > from)) throw new Error('The range must end after it starts')
    this.seek(from)
    this.play()
    this.rangeEnd = to
  }

  private shuttleTo(speed: number): void {
    this.requireContent()
    const { time, duration } = this.state.get()
    this.rangeEnd = null
    // Playing forward from the very end starts again from the top.
    this.timeAtStart = speed > 0 && time >= duration ? 0 : time
    this.clockStart = performance.now()
    this.state.set({ speed, time: this.timeAtStart })
    // Take effect now, not on the next animation frame.
    this.present(this.timeAtStart)
    this.startLoop()
  }

  private requireContent(): void {
    const { mode, item, duration } = this.state.get()
    if (mode === 'source' ? !item : !duration) throw new Error(mode === 'source' ? 'Open a file in the viewer first' : 'The timeline is empty')
  }

  private halt(): void {
    this.stopLoop()
    this.rangeEnd = null
    this.media?.pause()
    this.mix?.stop()
    this.state.set({ speed: 0 })
  }

  private list(): Segment[] {
    const { mode, item } = this.state.get()
    if (mode === 'timeline') return this.timeline ? segments(this.timeline) : []
    if (!item) return []
    // A source file is a one-clip timeline at speed 1.
    const clip = { type: 'clip', id: item.id, asset: item.id, speed: 1, volume: 1 } as Segment['clip']
    return [{ clip, start: 0, end: item.info?.durationSeconds ?? 0, sourceStart: 0 }]
  }

  private urlFor(segment: Segment): string | null {
    const { mode, item } = this.state.get()
    return mode === 'source' && item ? playbackUrl(item) : this.resolve(segment.clip.asset)
  }

  /** Shows `time`: the right file at the right moment, playing or still. */
  private present(time: number): void {
    const media = this.media
    if (!media) return
    if (this.state.get().mode === 'timeline') this.mix?.tick(time, this.state.get().speed)
    const segment = segmentAt(this.list(), time)
    const url = segment && this.urlFor(segment)
    const timeline = this.state.get().mode === 'timeline'
    const framing = timeline && segment ? framingAt(segment.clip, Math.round((time - segment.start) * this.fps)) : null
    const current = this.state.get().framing
    this.state.set({
      gap: !url,
      clipId: timeline ? (segment?.clip.id ?? null) : null,
      // Keep the same object while it doesn't change, so the viewer doesn't redraw every frame.
      framing: framing && current && framing.zoom === current.zoom && framing.x === current.x ? current : framing
    })
    if (!segment || !url) return media.pause()

    if (url !== this.source) {
      this.source = url
      this.pendingSeek = null
      media.src = url
    }
    media.volume = Math.min(1, segment.clip.volume)
    const target = sourceTime(segment, time)
    const { speed } = this.state.get()
    if (speed > 0) {
      media.playbackRate = Math.min(16, Math.max(0.0625, speed * segment.clip.speed))
      if (Math.abs(media.currentTime - target) > DRIFT) this.moveTo(media, target)
      if (media.paused) void media.play().catch(() => undefined)
    } else {
      media.pause()
      // Only seek when it would show a different frame; updates arrive far more often than that.
      if (this.pendingSeek !== null || Math.abs(media.currentTime - target) > 0.5 / this.fps) this.moveTo(media, target)
    }
  }

  private moveTo(media: HTMLMediaElement, time: number): void {
    if (media.seeking) this.pendingSeek = time
    else media.currentTime = time
  }

  private startLoop(): void {
    this.stopLoop()
    const tick = (now: number) => {
      const { speed, duration } = this.state.get()
      let time = this.timeAtStart + ((now - this.clockStart) / 1000) * speed
      const stopAt = this.rangeEnd ?? duration
      if ((speed < 0 && time <= 0) || time >= stopAt) {
        time = Math.min(Math.max(0, time), stopAt)
        this.halt()
        this.state.set({ time })
        return this.present(time)
      }
      this.state.set({ time })
      this.present(time)
      this.loop = requestAnimationFrame(tick)
    }
    this.loop = requestAnimationFrame(tick)
  }

  private stopLoop(): void {
    cancelAnimationFrame(this.loop)
    this.loop = 0
  }
}

export const player = new Player()
