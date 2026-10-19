import { describe, expect, it } from 'vitest'
import { applyOps, normalise, type TextItem } from '@timeline'
import { addTitleOps } from './captions'

const t = normalise({ fps: 30, tracks: [{ id: 'v1', kind: 'video', items: [] }] })

describe('titles', () => {
  it('adds a text track the first time, then 2.5 s titles at the playhead', () => {
    let doc = applyOps(t, addTitleOps(t, 'Big news', 30))
    expect(doc.tracks.map((tr) => tr.kind)).toEqual(['video', 'text'])
    const [title] = doc.tracks[1].items as TextItem[]
    expect(title).toMatchObject({ at: 30, dur: 75, text: 'Big news', style: 'studio', transform: { y: 0.72 } })
    // A second title under the same playhead starts after the first instead of overlapping it.
    doc = applyOps(doc, addTitleOps(doc, 'Second', 40, 'top'))
    const second = doc.tracks[1].items.find((i) => i.type === 'text' && i.text === 'Second') as TextItem
    expect(second).toMatchObject({ at: 105, transform: { y: 0.3 } })
  })
})
