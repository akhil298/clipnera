import { normalise } from '@timeline'
import { describe, expect, it } from 'vitest'
import { layersAt, type Layer } from './layers'

const t = normalise({
  version: 1, fps: 30, width: 1920, height: 1080, look: 'natural',
  assets: {
    a: { id: 'a', kind: 'video', key: 'a.mp4', frames: 900 },
    b: { id: 'b', kind: 'video', key: 'b.mp4', frames: 900 },
    i: { id: 'i', kind: 'image', key: 'i.png', frames: 1 }
  },
  tracks: [
    { id: 'v1', kind: 'video', items: [{ type: 'clip', id: 'c1', at: 0, asset: 'a', src_in: 0, src_out: 300 }] },
    { id: 'o1', kind: 'overlay', items: [
      { type: 'clip', id: 'br', at: 30, asset: 'b', src_in: 60, src_out: 120, speed: 2, transition_in: { type: 'fade', frames: 10 } },
      { type: 'clip', id: 'pip', at: 30, asset: 'i', src_in: 0, src_out: 60, transform: { x: 0.8, y: 0.25, scale: 0.3 } }
    ] },
    { id: 'g1', kind: 'graphic', items: [
      { type: 'graphic', id: 'fl', at: 35, dur: 2, extra: { solid: '#FFFFFF' } },
      { type: 'graphic', id: 'gl', at: 30, dur: 30, extra: { graphic: 'glitch_bars' } }
    ] },
    { id: 'g2', kind: 'graphic', hidden: true, items: [{ type: 'graphic', id: 'off', at: 0, dur: 300, extra: { solid: '#000' } }] }
  ]
})

describe('layers over the picture, as the export draws them', () => {
  it('shows nothing over the main picture where nothing is placed', () => {
    expect(layersAt(t, 0.5)).toEqual([])
  })

  it('stacks B-roll, picture-in-picture, flashes and graphics in track order, fading the B-roll in', () => {
    const at = layersAt(t, 35 / 30)
    expect(at.map((l) => [l.kind, l.id])).toEqual([['video', 'br'], ['image', 'pip'], ['solid', 'fl'], ['graphic', 'gl']])
    const broll = at[0] as Extract<Layer, { kind: 'video' | 'image' }>
    // 5 frames into a 2× clip that starts 2 s into its footage, half faded in.
    expect(broll.sourceTime).toBeCloseTo(2 + (5 / 30) * 2)
    expect(broll.opacity).toBeCloseTo(0.5)
    expect(at[1]).toMatchObject({ scale: 0.3, x: 0.8, y: 0.25 })
    expect(at[3]).toMatchObject({ graphic: 'glitch_bars', offset: 5 / 30 })
  })

  it('drops a layer once it ends', () => {
    expect(layersAt(t, 38 / 30).map((l) => l.id)).toEqual(['br', 'pip', 'gl'])
  })
})
