import type { Command } from './registry'

/**
 * Scores how well `query` matches a command: every query character must appear in order in
 * its title (or id/category); runs of matching characters and word starts score higher.
 * Returns -1 for no match.
 */
export function score(query: string, command: Pick<Command<unknown>, 'title' | 'id' | 'category'>): number {
  const q = query.trim().toLowerCase()
  if (!q) return 0
  let best = -1
  for (const text of [command.title, `${command.category} ${command.title}`, command.id]) {
    const t = text.toLowerCase()
    let at = 0
    let total = 0
    let run = 0
    for (const ch of q) {
      const found = t.indexOf(ch, at)
      if (found < 0) {
        total = -1
        break
      }
      run = found === at ? run + 1 : 1
      total += run + (found === 0 || t[found - 1] === ' ' || t[found - 1] === '.' ? 3 : 0)
      at = found + 1
    }
    best = Math.max(best, total)
  }
  return best
}

/** Commands the palette offers for `query`, best first. */
export function search(commands: readonly Command<unknown>[], query: string): Command<unknown>[] {
  return commands
    .filter((c) => !c.needsArgs)
    .map((c) => ({ c, s: score(query, c) }))
    .filter(({ s }) => s >= 0)
    .sort((a, b) => b.s - a.s || a.c.title.localeCompare(b.c.title))
    .map(({ c }) => c)
}
