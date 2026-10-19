import { describe, expect, it } from 'vitest'
import { applyOps, normalise } from '@timeline'
import { batches, restoreOps } from './takes'

const assets = { v: { id: 'v', kind: 'video', key: 'k/v', frames: 900, has_audio: true }, m: { id: 'm', kind: 'audio', key: 'k/m', frames: 900 } }
const clip = (id: string, at: number, out: number) => ({ type: 'clip', id, at, asset: 'v', src_in: 0, src_out: out })

const take = normalise({
  fps: 30, look: 'warm_film', assets,
  tracks: [
    { id: 'v1', kind: 'video', items: [clip('a', 0, 60), clip('b', 60, 120)] },
    { id: 't1', kind: 'text', items: [{ type: 'text', id: 'x', at: 0, text: 'Hook', style: 'title', dur: 30 }] }
  ],
  captions: { enabled: true, style: 'karaoke', follow: 'v1' }
})

describe('restoring a take', () => {
  it('turns a later edit back into the take exactly', () => {
    const later = normalise({
      fps: 30, look: 'vivid', assets,
      tracks: [
        { id: 'v1', kind: 'video', items: [clip('a', 0, 30), clip('c', 30, 90)] },
        { id: 'a1', kind: 'audio', items: [{ type: 'clip', id: 'mm', at: 0, asset: 'm', src_in: 0, src_out: 90 }] }
      ]
    })
    expect(applyOps(later, restoreOps(later, take))).toEqual(take)
  })

  it('turns captions back off when the take had none', () => {
    const plain = normalise({ fps: 30, assets, tracks: [{ id: 'v1', kind: 'video', items: [clip('a', 0, 60)] }] })
    const withCaptions = applyOps(plain, [{ op: 'set_captions', enabled: true, follow: 'v1' }])
    expect(applyOps(withCaptions, restoreOps(withCaptions, plain)).captions?.enabled).toBe(false)
  })

  it('splits big restores into changes the backend takes', () => {
    expect(batches(Array.from({ length: 450 }, () => ({ op: 'remove_marker', f: 0 }) as const)).map((b) => b.length)).toEqual([200, 200, 50])
  })
})
