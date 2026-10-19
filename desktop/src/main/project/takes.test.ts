import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { normalise } from '@timeline'
import { AUTO_TAKES, TakesStore } from './takes'

const t = normalise({ fps: 30, tracks: [{ id: 'v1', kind: 'video', items: [] }] })
const store = () => new TakesStore(join(mkdtempSync(join(tmpdir(), 'takes-')), 'p', 'takes.json'))

describe('Takes', () => {
  it('saves versions newest first and removes them', async () => {
    const takes = store()
    await takes.save('Tight cut', t, 'manual')
    const [second, first] = await takes.save('  Story cut  ', t, 'manual')
    expect([second.name, first.name]).toEqual(['Story cut', 'Tight cut'])
    expect((await takes.remove(first.id)).map((x) => x.name)).toEqual(['Story cut'])
  })

  it('keeps only the latest automatic takes, never dropping saved ones for them', async () => {
    const takes = store()
    await takes.save('Mine', t, 'manual')
    for (let i = 0; i < AUTO_TAKES + 3; i++) await takes.save(`Before ${i}`, t, 'auto')
    const all = await takes.list()
    expect(all.filter((x) => x.source === 'auto')).toHaveLength(AUTO_TAKES)
    expect(all.some((x) => x.name === 'Mine')).toBe(true)
    expect(all[0].name).toBe(`Before ${AUTO_TAKES + 2}`)
  })
})
