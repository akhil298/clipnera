import type { PreviewWord } from '../../../shared/api'

export interface CaptionLine {
  words: PreviewWord[]
  start: number
  end: number
}

// A pause this long starts a new caption line.
const PAUSE = 0.6
// A line stays up this long after its last word unless the next line starts sooner.
const HOLD = 0.4

/** Words grouped into lines of at most `maxWords`, broken at pauses (like the ASS generator's lines). */
export function captionLines(words: readonly PreviewWord[], maxWords: number): CaptionLine[] {
  const lines: CaptionLine[] = []
  for (const word of words) {
    const last = lines.at(-1)
    if (last && last.words.length < Math.max(1, maxWords) && word.start - last.end < PAUSE) {
      last.words.push(word)
      last.end = word.end
    } else {
      lines.push({ words: [word], start: word.start, end: word.end })
    }
  }
  return lines
}

/** The line on screen at `time`, and which of its words is being said (-1 between words). */
export function lineAt(lines: readonly CaptionLine[], time: number): { line: CaptionLine; active: number } | null {
  const index = lines.findIndex((line, i) => time >= line.start && time < Math.min(line.end + HOLD, lines[i + 1]?.start ?? Infinity))
  if (index < 0) return null
  const line = lines[index]
  return { line, active: line.words.findIndex((w) => time >= w.start && time < w.end) }
}
