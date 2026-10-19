import { describe, expect, it } from 'vitest'
import { normalise } from '@timeline'
import { segmentAt, segments, sourceTime, timelineSeconds } from './sequence'

const clip = (id: string, at: number, srcIn: number, srcOut: number, speed = 1) => ({ type: 'clip', id, at, asset: 'a', src_in: srcIn, src_out: srcOut, speed })
const t = normalise({
  fps: 30,
  assets: { a: { id: 'a', kind: 'video', key: 'k', frames: 900 } },
  tracks: [
    { id: 't1', kind: 'text', items: [] },
    { id: 'v1', kind: 'video', items: [clip('b', 120, 300, 360, 2), clip('a', 0, 30, 90)] }
  ]
})

describe('program playback maths', () => {
  it('lists the main video track in time order', () => {
    expect(segments(t).map((s) => [s.clip.id, s.start, s.end])).toEqual([['a', 0, 2], ['b', 4, 5]])
  })

  it('finds the clip under the playhead, and nothing in a gap', () => {
    const list = segments(t)
    expect(segmentAt(list, 1.9)?.clip.id).toBe('a')
    expect(segmentAt(list, 3)).toBeNull()
    expect(segmentAt(list, 5)).toBeNull()
  })

  it('maps timeline time to footage time, speed included', () => {
    const [a, b] = segments(t)
    expect(sourceTime(a, 1)).toBeCloseTo(2)
    expect(sourceTime(b, 4.5)).toBeCloseTo(11)
    expect(timelineSeconds(t)).toBe(5)
  })
})
