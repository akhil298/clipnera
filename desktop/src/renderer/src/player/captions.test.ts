import { describe, expect, it } from 'vitest'
import { captionLines, lineAt } from './captions'

const w = (word: string, start: number, end: number) => ({ word, start, end })
const words = [w('one', 0, 0.3), w('two', 0.35, 0.6), w('three', 0.65, 0.9), w('four', 0.95, 1.2), w('after', 2.5, 2.8)]

describe('caption lines', () => {
  it('groups words up to the line length and breaks at pauses', () => {
    expect(captionLines(words, 3).map((l) => l.words.map((x) => x.word).join(' '))).toEqual(['one two three', 'four', 'after'])
  })

  it('shows the line being said and highlights the current word', () => {
    const lines = captionLines(words, 3)
    expect(lineAt(lines, 0.4)).toMatchObject({ active: 1, line: { start: 0 } })
    expect(lineAt(lines, 0.62)?.active).toBe(-1)
    // Held briefly after the last word, then gone until the next line.
    expect(lineAt(lines, 1.4)?.line.words[0].word).toBe('four')
    expect(lineAt(lines, 2)).toBeNull()
    expect(lineAt(lines, 2.6)?.line.words[0].word).toBe('after')
  })
})
