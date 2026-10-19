import { describe, expect, it } from 'vitest'
import { normalise } from '@timeline'
import type { MediaItem } from '../../shared/media'
import { summarizeMedia, summarizeProject } from './summary'

const t = normalise({
  fps: 30, width: 1920, height: 1080,
  assets: { a: { id: 'a', kind: 'video', key: 'editor/u/p/x.mp4', frames: 300 } },
  tracks: [
    { id: 'v1', kind: 'video', items: [{ type: 'clip', id: 'c1', at: 0, asset: 'a', src_in: 0, src_out: 90, speed: 2 }] },
    { id: 't1', kind: 'text', items: [{ type: 'text', id: 'x', at: 15, text: 'Hook', style: 's', dur: 30 }] }
  ]
})
const media = [{ id: 'a', name: 'talk.mp4', path: '/t', kind: 'video', status: 'ready', progress: 1, info: { durationSeconds: 10 } }] as MediaItem[]

describe('what outside agents read', () => {
  it('summarizes the project in seconds and names', () => {
    const summary = summarizeProject('Ep 12', 4, t, media)
    expect(summary).toMatchObject({ title: 'Ep 12', version: 4, seconds: 1.5, size: '1920x1080', captions: null })
    expect(summary.tracks[0].items[0]).toEqual({ id: 'c1', type: 'clip', start: 0, end: 1.5, what: 'talk.mp4', speed: 2, volume: 1, zoom: 1 })
    expect(summary.tracks[1].items[0]).toMatchObject({ what: 'Hook', start: 0.5, end: 1.5 })
  })

  it('lists media with what the AI understood', () => {
    const [m] = summarizeMedia(media, { a: { asset_id: 'a', status: 'ready', stage: null, error: null, updated_at: '', findings: { summary: 'A talk', moments: [{ t0: 1, t1: 2, text: 'Line' }] } as never } })
    expect(m).toMatchObject({ name: 'talk.mp4', understanding: 'ready', summary: 'A talk', moments: [{ text: 'Line' }] })
  })
})
