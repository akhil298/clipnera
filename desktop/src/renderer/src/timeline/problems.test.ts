import { describe, expect, it } from 'vitest'
import { applyOps, normalise } from '@timeline'
import type { ProjectPreview } from '../../../shared/api'
import type { MediaItem } from '../../../shared/media'
import { closeGapOps, findProblems } from './problems'

const clip = (id: string, at: number, frames: number, extra: Record<string, unknown> = {}) => ({ type: 'clip', id, at, asset: 'v', src_in: 0, src_out: frames, ...extra })
const base = {
  fps: 10,
  assets: { v: { id: 'v', kind: 'video', key: 'k/v', frames: 1000, has_audio: true }, m: { id: 'm', kind: 'audio', key: 'k/m', frames: 1000 } }
}
const doc = (items: unknown[], more: Record<string, unknown> = {}) => normalise({ ...base, tracks: [{ id: 'v1', kind: 'video', items }], ...more })
const ids = (t: ReturnType<typeof doc>, preview: ProjectPreview | null = null, media: MediaItem[] = []) => findProblems(t, preview, media, () => true).map((p) => p.id)

describe('problems', () => {
  it('finds a gap, and closing it moves everything after it', () => {
    const t = doc([clip('a', 0, 20), clip('b', 30, 20), clip('c', 50, 10)])
    const [gap] = findProblems(t, null, [], () => true)
    expect(gap).toMatchObject({ id: 'gap-b', severity: 'warning', fix: { command: 'timeline.closeGap', args: { at: 30 } } })
    const closed = applyOps(t, closeGapOps(t, 30))
    expect(ids(closed)).toEqual([])
    expect(closed.tracks[0].items.map((i) => i.at).sort((x, y) => x - y)).toEqual([0, 20, 40])
  })

  it('flags flash frames, and not moving zooms (the export moves them too)', () => {
    const t = doc([clip('a', 0, 2), clip('b', 2, 20, { keyframes: { scale: [{ f: 0, v: 1 }, { f: 10, v: 1.2 }] } })])
    expect(ids(t)).toEqual(['flash-a'])
  })

  it("says what the export leaves out", () => {
    const t = normalise({
      ...base,
      tracks: [
        { id: 'v1', kind: 'video', items: [clip('a', 0, 50, { keyframes: { opacity: [{ f: 0, v: 0 }, { f: 8, v: 1 }] } })] },
        { id: 'a1', kind: 'audio', items: [{ type: 'sfx', id: 's1', at: 5, name: 'sparkle', dur: 5 }, { type: 'sfx', id: 's2', at: 15, name: 'whoosh', dur: 5 }, { type: 'clip', id: 'm1', at: 0, asset: 'm', src_in: 0, src_out: 10 }, { type: 'clip', id: 'm2', at: 20, asset: 'm', src_in: 0, src_out: 10 }] },
        { id: 'g1', kind: 'graphic', items: [{ type: 'graphic', id: 'f1', at: 10, dur: 2 }] }
      ]
    })
    // Every library sound and the graphics are in exports now; a fade on the main track and a second music clip aren't.
    expect(ids(t).sort()).toEqual(['fade-a', 'music-many'])
  })

  it('warns about captions over burned-in words and titles where captions sit', () => {
    const t = normalise({ ...base, tracks: [{ id: 'v1', kind: 'video', items: [clip('a', 0, 50)] }, { id: 't1', kind: 'text', items: [{ type: 'text', id: 'x', at: 10, text: 'Lower', style: 'studio', dur: 20, transform: { y: 0.72 } }] }], captions: { enabled: true, style: 'karaoke', follow: 'v1' } })
    const preview = { version: 1, look: 'natural', caption_style: 'karaoke', caption_look: null, words: [{ word: 'hi', start: 1.5, end: 2 }], texts: [{ kind: 'line', text: 'Lower', at: 1, dur: 2 }], sounds: [] } as ProjectPreview
    const media = [{ id: 'v', name: 'talk.mp4', path: '/t', kind: 'video', status: 'ready', progress: 1, onScreenText: { share: 0.3, examples: ['Hello'] } }] as MediaItem[]
    const found = findProblems(t, preview, media, () => true)
    expect(found.map((p) => p.id)).toEqual(['burned-in', 'clash-x'])
    expect(found[1].fix).toMatchObject({ command: 'text.place', args: { item: 'x', place: 'middle' } })
  })

  it('notices footage it cannot find, and an empty main track', () => {
    expect(findProblems(doc([clip('a', 0, 20)]), null, [], () => false).map((p) => p.id)).toEqual(['missing-a'])
    expect(ids(normalise({ ...base, tracks: [{ id: 'v1', kind: 'video', items: [] }, { id: 't1', kind: 'text', items: [{ type: 'text', id: 'x', at: 0, text: 'Hi', style: 's', dur: 5 }] }] }))).toEqual(['no-main'])
  })
})
