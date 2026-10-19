import { describe, expect, it } from 'vitest'
import { framingAt, framingOf, placement, valueAt } from './framing'

const base = { transform: { x: 0.5, y: 0.5, scale: 1, rotation: 0 }, keyframes: {} }

describe('framing like the render', () => {
  it('moves a zoom between its keyframes with the ease of the point it moves towards', () => {
    const points = [{ f: 10, v: 1, ease: 'linear' as const }, { f: 20, v: 2, ease: 'in' as const }]
    expect([0, 10, 15, 20, 30].map((f) => valueAt(points, f))).toEqual([1, 1, 1.25, 2, 2])
    expect(valueAt([{ f: 0, v: 0, ease: 'linear' }, { f: 10, v: 1, ease: 'out' }], 5)).toBe(0.75)
    expect(valueAt([{ f: 0, v: 0, ease: 'linear' }, { f: 10, v: 1, ease: 'in_out' }], 2.5)).toBe(0.125)
    expect(framingAt({ ...base, keyframes: { scale: points, x: [{ f: 0, v: 1.4, ease: 'linear' }] } }, 15)).toEqual({ zoom: 1.25, x: 1 })
    expect(framingAt({ ...base, keyframes: { scale: [{ f: 0, v: 0.5, ease: 'linear' }] } }, 0).zoom).toBe(1)
  })

  it('gives a moving zoom at its average for panels, never below 1×', () => {
    expect(framingOf({ ...base, keyframes: { scale: [{ f: 0, v: 1, ease: 'linear' }, { f: 10, v: 1.2, ease: 'linear' }] } })).toEqual({ zoom: 1.1, x: 0.5 })
    expect(framingOf({ ...base, transform: { ...base.transform, scale: 0.8 } }).zoom).toBe(1)
  })

  it('fills a same-shape frame exactly at 1×', () => {
    expect(placement(1920, 1080, 960, 540, { zoom: 1, x: 0.5 })).toEqual({ left: -0, top: -0, width: 960, height: 540 })
  })

  it('zooms in around the crop centre, kept inside the picture', () => {
    const p = placement(1920, 1080, 960, 540, { zoom: 2, x: 0.5 })
    expect(p.width).toBe(1920)
    expect(p.left).toBe(-480)
    // A centre near the edge stops at the edge instead of showing past it.
    expect(placement(1920, 1080, 960, 540, { zoom: 2, x: 0 }).left).toBe(-0)
  })

  it('crops landscape footage to fill a vertical frame, as the export does', () => {
    const p = placement(1920, 1080, 540, 960, { zoom: 1, x: 0.5 })
    expect(p.height).toBeCloseTo(960)
    expect(p.width).toBeCloseTo(1706.67, 1)
    expect(p.left).toBeCloseTo(-583.33, 1)
  })
})
