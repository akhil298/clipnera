import { describe, expect, it } from 'vitest'
import { apply, hasVignette, lookMatrix } from './looks'

const grey: [number, number, number] = [0.5, 0.5, 0.5]

describe('looks as colour matrices', () => {
  it('black & white drops colour and pushes contrast', () => {
    const [r, g, b] = apply(lookMatrix('bw_punch'), [0.8, 0.2, 0.2])
    expect(r).toBeCloseTo(g, 5)
    expect(g).toBeCloseTo(b, 5)
    expect(apply(lookMatrix('bw_punch'), [0.9, 0.9, 0.9])[0]).toBeCloseTo(1, 2)
  })

  it('keeps mid grey where contrast pivots, and brightness lifts it', () => {
    expect(apply(lookMatrix('vivid'), grey)[0]).toBeCloseTo(0.5, 5)
    expect(apply(lookMatrix('clean_bright'), grey)[0]).toBeCloseTo(0.53, 5)
    expect(apply(lookMatrix('moody'), grey)[0]).toBeCloseTo(0.47, 5)
  })

  it('warm film tints grey towards red and away from blue', () => {
    const [r, , b] = apply(lookMatrix('warm_film'), grey)
    expect(r).toBeGreaterThan(0.5)
    expect(b).toBeLessThan(0.5)
  })

  it('vivid saturates colour; unknown looks fall back to natural', () => {
    const vivid = apply(lookMatrix('vivid'), [0.6, 0.4, 0.4])
    expect(vivid[0] - vivid[1]).toBeGreaterThan(0.2)
    expect(lookMatrix('no-such-look')).toEqual(lookMatrix('natural'))
    expect(hasVignette('moody')).toBe(true)
  })
})
