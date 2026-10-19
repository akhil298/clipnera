import { describe, expect, it } from 'vitest'
import { fileName } from './service'

describe('export file names', () => {
  it('uses the project title and the time, safe for Finder', () => {
    const at = new Date(2026, 9, 18, 17, 5)
    expect(fileName('Founder chat ep 12', at)).toBe('Founder chat ep 12 2026-10-18 17-05.mp4')
    expect(fileName('a/b: c?', at)).toBe('a b c 2026-10-18 17-05.mp4')
    expect(fileName('   ', at)).toBe('Clipnera edit 2026-10-18 17-05.mp4')
  })
})
