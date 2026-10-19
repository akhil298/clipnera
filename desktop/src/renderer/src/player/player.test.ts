import { beforeAll, describe, expect, it, vi } from 'vitest'
import { normalise } from '@timeline'
import type { MediaItem } from '../../../shared/media'
import { Player } from './player'

const ITEM: MediaItem = {
  id: 'a',
  path: '/a.mov',
  name: 'a.mov',
  kind: 'video',
  status: 'ready',
  progress: 1,
  info: { durationSeconds: 10, fileSize: 1, hasVideo: true, hasAudio: false, fps: 10 }
}

/** Two clips from two files: 0–2 s shows a.mp4 from 1 s, 2–3 s shows b.mp4 from 0 s. */
const TIMELINE = normalise({
  fps: 10,
  assets: { a: { id: 'a', kind: 'video', key: 'k/a', frames: 100 }, b: { id: 'b', kind: 'video', key: 'k/b', frames: 100 } },
  tracks: [
    {
      id: 'v1',
      kind: 'video',
      items: [
        { type: 'clip', id: 'c1', at: 0, asset: 'a', src_in: 10, src_out: 30 },
        { type: 'clip', id: 'c2', at: 20, asset: 'b', src_in: 0, src_out: 10 }
      ]
    }
  ]
})

/** Stands in for the video element: a seek stays "in progress" until the test finishes it. */
class FakeMedia {
  seeking = false
  seeks: number[] = []
  src = ''
  paused = true
  volume = 1
  playbackRate = 1
  onseeked: (() => void) | null = null
  private time = 0

  get currentTime() {
    return this.time
  }
  set currentTime(t: number) {
    this.time = t
    this.seeking = true
    this.seeks.push(t)
  }
  finishSeek() {
    this.seeking = false
    this.onseeked?.()
  }
  pause() {
    this.paused = true
  }
  async play() {
    this.paused = false
  }
}

function setUp(mode: 'source' | 'timeline' = 'source') {
  const player = new Player()
  const media = new FakeMedia()
  player.attach(media as unknown as HTMLMediaElement)
  if (mode === 'source') player.open(ITEM)
  else player.setTimeline(TIMELINE, (id) => `clipnera-media://${id}/proxy.mp4`)
  media.finishSeek()
  media.seeks = []
  return { player, media }
}

describe('Player', () => {
  // The playback loop is driven by animation frames; these tests only step and seek.
  beforeAll(() => {
    vi.stubGlobal('requestAnimationFrame', () => 0)
    vi.stubGlobal('cancelAnimationFrame', () => undefined)
  })

  it('needs something to show before it can play', () => {
    const player = new Player()
    expect(() => player.seek(1)).toThrow('The timeline is empty')
    expect(() => player.open({ ...ITEM, status: 'preparing' })).toThrow("a.mov isn't ready yet")
  })

  it('queues seeks while one is in progress, keeping only the latest', () => {
    const { player, media } = setUp()
    player.step(1)
    player.step(1)
    player.step(1)
    expect(media.seeks).toEqual([0.15])
    media.finishSeek()
    expect(media.seeks).toEqual([0.15, 0.35])
  })

  it('counts frame steps from where it is going, not where the element still is', () => {
    const { player } = setUp()
    for (let i = 0; i < 3; i++) player.step(1)
    player.step(-1)
    expect(player.state.get().time).toBeCloseTo(0.25)
  })

  it('keeps seeks inside what is open', () => {
    const { player } = setUp()
    player.seek(99)
    expect(player.state.get().time).toBe(10)
    player.seek(-5)
    expect(player.state.get().time).toBe(0)
  })

  it('shows the right file and moment for each clip of the timeline', () => {
    const { player, media } = setUp('timeline')
    expect(player.state.get()).toMatchObject({ mode: 'timeline', duration: 3, clipId: 'c1', gap: false })
    player.seek(1.5)
    expect(media.src).toBe('clipnera-media://a/proxy.mp4')
    expect(media.currentTime).toBeCloseTo(2.5)
    media.finishSeek()
    player.seek(2.5)
    expect(media.src).toBe('clipnera-media://b/proxy.mp4')
    expect(media.currentTime).toBeCloseTo(0.5)
    expect(player.state.get().clipId).toBe('c2')
  })

  it('refuses a range that ends before it starts', () => {
    const { player } = setUp()
    expect(() => player.playRange(5, 2)).toThrow('The range must end after it starts')
  })

  it('closing a source file goes back to the timeline', () => {
    const { player } = setUp()
    player.close()
    expect(player.state.get()).toMatchObject({ mode: 'timeline', item: null })
  })
})
