import { describe, expect, it } from 'vitest'
import { normalise } from '@timeline'
import { ducked, loopedTime, mixPlan } from './audio'

const t = normalise({
  fps: 10,
  assets: {
    v: { id: 'v', kind: 'video', key: 'k/v', frames: 100, has_audio: true },
    m: { id: 'm', kind: 'audio', key: 'k/m', frames: 600, has_audio: true },
    m2: { id: 'm2', kind: 'audio', key: 'k/m2', frames: 600, has_audio: true }
  },
  tracks: [
    { id: 'v1', kind: 'video', items: [{ type: 'clip', id: 'c1', at: 0, asset: 'v', src_in: 0, src_out: 50 }] },
    {
      id: 'a1',
      kind: 'audio',
      items: [
        { type: 'clip', id: 'music', at: 0, asset: 'm', src_in: 20, src_out: 120, volume: 0.4 },
        { type: 'sfx', id: 's1', at: 30, name: 'whoosh', dur: 5 },
        { type: 'sfx', id: 's2', at: 10, name: 'sparkle', dur: 5 }
      ]
    },
    { id: 'a2', kind: 'audio', items: [{ type: 'clip', id: 'other', at: 0, asset: 'm2', src_in: 0, src_out: 100 }] }
  ]
})

const plan = mixPlan(t, (id) => `clipnera-media://${id}/proxy.m4a`, (item) => `/static/sfx/${item.name}.wav`)

describe('the viewer mix', () => {
  it('plays the first audio clip as the music, on to the end of the edit, as the export does', () => {
    expect(plan.music).toMatchObject({ id: 'music', url: 'clipnera-media://m/proxy.m4a', start: 0, sourceStart: 2, speed: 1, volume: 0.4 })
    expect(plan.music!.end).toBeGreaterThanOrEqual(10)
  })

  it('loops the music: from the clip start point, then the whole file again', () => {
    const cue = { start: 1, sourceStart: 2, speed: 1 }
    // A 10 s file entered 2 s in: 8 s play first, then it starts over at 0.
    expect([2, 9, 10, 11, 19].map((t) => loopedTime(cue, t, 10))).toEqual([3, 0, 1, 2, 0])
    expect(loopedTime(cue, 9, Number.NaN)).toBe(10)
  })

  it('lists sound effects in time order, at the level the export plays them', () => {
    expect(plan.sounds.map((s) => [s.id, s.at, +s.volume.toFixed(3)])).toEqual([['s2', 1, 0.251], ['s1', 3, 0.251]])
  })

  it('ducks the music where the main track has speech', () => {
    expect(ducked(plan, 2)).toBe(true)
    expect(ducked(plan, 6)).toBe(false)
  })
})
