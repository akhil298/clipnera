import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'

export const MAX_RULES = 20
export const MAX_RULE_CHARS = 200

/** A project's Edit Rules: plain sentences the AI follows on every request, kept on this Mac. */
export class RulesStore {
  constructor(private readonly file: string) {}

  async get(): Promise<string[]> {
    try {
      const rules = JSON.parse(await readFile(this.file, 'utf8'))
      return Array.isArray(rules) ? rules.filter((r): r is string => typeof r === 'string') : []
    } catch {
      return []
    }
  }

  /** Saves the list as given, after tidying: no blanks, no repeats, within the backend's limits. */
  async set(rules: unknown): Promise<string[]> {
    if (!Array.isArray(rules)) throw new Error('rules must be a list')
    const tidy = [...new Set(rules.filter((r): r is string => typeof r === 'string').map((r) => r.trim()).filter(Boolean))]
    if (tidy.length > MAX_RULES) throw new Error(`Keep it to ${MAX_RULES} rules`)
    if (tidy.some((r) => r.length > MAX_RULE_CHARS)) throw new Error(`Keep each rule under ${MAX_RULE_CHARS} characters`)
    await mkdir(dirname(this.file), { recursive: true })
    await writeFile(this.file, JSON.stringify(tidy))
    return tidy
  }
}
