import { describe, expect, it } from 'vitest'
import { applyOps, duration, itemEnd, normalise, type Asset, type ClipItem, type Timeline } from '@timeline'
import { appendClip, moveItem, removeItems, setSpeed, setVolume, splitAt, trimEnd, trimStart } from './edits'

const ASSET: Asset = { id: 'a1', kind: 'video', key: 'editor/u/p/a.mp4', proxy: null, frames: 300, width: 1280, height: 720, has_audio: true }
const AUDIO: Asset = { ...ASSET, id: 'm1', kind: 'audio', frames: 90, width: null, height: null }

function start(): Timeline {
  return normalise({ fps: 30, width: 1920, height: 1080, assets: { a1: ASSET, m1: AUDIO }, tracks: [{ id: 'v1', kind: 'video', items: [] }] })
}

const run = (t: Timeline, ops: ReturnType<typeof appendClip>) => applyOps(t, ops)
const clips = (t: Timeline, track = 'v1') => [...(t.tracks.find((tr) => tr.id === track)!.items as ClipItem[])].sort((a, b) => a.at - b.at)

function twoClips(): Timeline {
  let t = start()
  t = run(t, appendClip(t, ASSET))
  return run(t, appendClip(t, ASSET))
}

describe('timeline edits (checked by the shared applyOps)', () => {
  it('appends clips end to end, and audio to its own track', () => {
    let t = twoClips()
    expect(clips(t).map((c) => [c.at, c.src_out])).toEqual([[0, 300], [300, 300]])
    t = run(t, appendClip(t, AUDIO))
    expect(t.tracks.map((tr) => [tr.id, tr.kind])).toEqual([['v1', 'video'], ['a1', 'audio']])
    expect(clips(t, 'a1')[0]).toMatchObject({ at: 0, asset: 'm1' })
  })

  it('splits the main-track clip under the playhead when nothing is selected', () => {
    let t = twoClips()
    t = run(t, splitAt(t, 100, []))
    expect(clips(t).map((c) => [c.at, c.src_in, c.src_out])).toEqual([[0, 0, 100], [100, 100, 300], [300, 0, 300]])
    expect(splitAt(t, 300, [])).toEqual([])
  })

  it('ripple delete closes the gap; lift leaves it', () => {
    const t = twoClips()
    const first = clips(t)[0].id
    expect(clips(run(t, removeItems(t, [first], true)))[0].at).toBe(0)
    expect(clips(run(t, removeItems(t, [first], false)))[0].at).toBe(300)
    expect(clips(run(t, removeItems(t, clips(t).map((c) => c.id), true)))).toEqual([])
  })

  it('trims either end without overlapping the neighbour', () => {
    let t = twoClips()
    const [a, b] = clips(t).map((c) => c.id)
    t = run(t, trimEnd(t, a, 200))
    expect(itemEnd(clips(t)[0])).toBe(200)
    t = run(t, trimStart(t, b, 50))
    expect(clips(t)[1]).toMatchObject({ at: 350, src_in: 50 })
    // Growing the second clip back to the left moves before it trims.
    t = run(t, trimStart(t, b, 0))
    expect(clips(t)[1]).toMatchObject({ at: 300, src_in: 0 })
    expect(trimEnd(t, a, 9999)).toEqual([{ op: 'trim_item', item: a, src_out: 300 }])
  })

  it('speed changes push or pull what follows', () => {
    let t = twoClips()
    const [a, b] = clips(t).map((c) => c.id)
    t = run(t, setSpeed(t, a, 2))
    expect(clips(t).find((c) => c.id === b)!.at).toBe(150)
    t = run(t, setSpeed(t, a, 0.5))
    expect(clips(t).find((c) => c.id === b)!.at).toBe(600)
    expect(duration(t)).toBe(900)
  })

  it('moves and sets volume within the rules', () => {
    const t = twoClips()
    const [a] = clips(t).map((c) => c.id)
    expect(() => run(t, moveItem(t, a, 100))).toThrow(/overlap/i)
    expect(clips(run(t, setVolume(t, a, 5)))[0].volume).toBe(2)
  })
})
