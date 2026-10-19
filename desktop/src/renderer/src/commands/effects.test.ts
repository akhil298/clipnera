import { describe, expect, it } from 'vitest'
import { applyOps, normalise, type ClipItem } from '@timeline'
import { frameOps, zoomOps } from './effects'

const t = normalise({
  fps: 30,
  assets: { v: { id: 'v', kind: 'video', key: 'k/v', frames: 300 } },
  tracks: [{ id: 'v1', kind: 'video', items: [{ type: 'clip', id: 'c1', at: 0, asset: 'v', src_in: 0, src_out: 300,
    keyframes: { scale: [{ f: 0, v: 1 }, { f: 30, v: 1.2 }], opacity: [{ f: 0, v: 0 }, { f: 8, v: 1 }] } }] }]
})
const clip = (doc = t) => doc.tracks[0].items[0] as ClipItem

describe('effects', () => {
  it('a held zoom replaces a moving one and keeps other keyframes', () => {
    const doc = applyOps(t, zoomOps(clip(), 1.14))
    expect(clip(doc).transform.scale).toBe(1.14)
    expect(Object.keys(clip(doc).keyframes)).toEqual(['opacity'])
  })

  it('framing moves the crop centre within the picture', () => {
    expect(clip(applyOps(t, frameOps(clip(), 0.3))).transform.x).toBe(0.3)
    expect(() => frameOps(clip(), 1.5)).toThrow('between 0 (left) and 1 (right)')
    expect(() => zoomOps(clip(), 0.5)).toThrow('between 1× and 3×')
  })
})
