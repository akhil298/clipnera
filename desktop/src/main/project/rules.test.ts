import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { RulesStore } from './rules'

describe('Edit Rules', () => {
  const store = () => new RulesStore(join(mkdtempSync(join(tmpdir(), 'rules-')), 'p', 'rules.json'))

  it('keeps a tidy list per project', async () => {
    const rules = store()
    expect(await rules.get()).toEqual([])
    expect(await rules.set(['  Never cut mid-sentence ', '', 'Never cut mid-sentence', 'Captions: max 3 words'])).toEqual(['Never cut mid-sentence', 'Captions: max 3 words'])
    expect(await rules.get()).toEqual(['Never cut mid-sentence', 'Captions: max 3 words'])
  })

  it('stays within what the backend takes', async () => {
    await expect(store().set(Array.from({ length: 21 }, (_, i) => `rule ${i}`))).rejects.toThrow('20 rules')
    await expect(store().set(['x'.repeat(201)])).rejects.toThrow('200 characters')
  })
})
