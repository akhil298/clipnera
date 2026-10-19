import { describe, expect, it } from 'vitest'
import { applyOps, normalise, type ClipItem, type SfxItem } from '@timeline'
import { addMusicOps, addSoundOps, MUSIC_VOLUME } from './sounds'

const t = normalise({
  fps: 30,
  assets: {
    v: { id: 'v', kind: 'video', key: 'k/v', frames: 300, has_audio: true },
    m: { id: 'm', kind: 'audio', key: 'k/m', frames: 3000, has_audio: true }
  },
  tracks: [{ id: 'v1', kind: 'video', items: [{ type: 'clip', id: 'c1', at: 0, asset: 'v', src_in: 0, src_out: 300 }] }]
})

describe('sounds and music', () => {
  it('puts a library sound at the playhead on its own track, storing its path', () => {
    let doc = applyOps(t, addSoundOps(t, { id: 'whoosh', url: 'http://localhost:8000/static/sfx/whoosh.wav', seconds: 0.8 }, 60))
    const [sound] = doc.tracks.find((tr) => tr.id === 'sfx')!.items as SfxItem[]
    expect(sound).toMatchObject({ at: 60, dur: 24, name: 'whoosh', extra: { url: '/static/sfx/whoosh.wav' } })
    // A second sound at the same spot goes after the first.
    doc = applyOps(doc, addSoundOps(doc, { id: 'pop', url: '/static/sfx/pop.wav', seconds: 0.3 }, 70))
    expect((doc.tracks.find((tr) => tr.id === 'sfx')!.items as SfxItem[]).map((s) => s.at).sort((a, b) => a - b)).toEqual([60, 84])
  })

  it('lays music under the whole edit, cut to its length, at −14 dB', () => {
    const doc = applyOps(t, addMusicOps(t, 'm'))
    const [music] = doc.tracks.find((tr) => tr.id === 'music')!.items as ClipItem[]
    expect(music).toMatchObject({ at: 0, src_in: 0, src_out: 300, volume: MUSIC_VOLUME })
    expect(() => addMusicOps(t, 'v')).toThrow('Pick an audio file')
  })
})
