import { randomUUID } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import type { Timeline } from '@timeline'
import type { Take } from '../../shared/takes'

// Saved before every AI request; only the latest few are worth keeping.
export const AUTO_TAKES = 10
export const MANUAL_TAKES = 30

/** A project's Takes: whole versions of the edit, newest first. */
export class TakesStore {
  constructor(private readonly file: string) {}

  async list(): Promise<Take[]> {
    try {
      const takes = JSON.parse(await readFile(this.file, 'utf8'))
      return Array.isArray(takes) ? takes : []
    } catch {
      return []
    }
  }

  async save(name: string, timeline: Timeline, source: Take['source']): Promise<Take[]> {
    const label = name.trim().slice(0, 80) || 'Untitled take'
    const take: Take = { id: randomUUID(), name: label, savedAt: new Date().toISOString(), source, timeline }
    const all = [take, ...(await this.list())]
    const keep = [...all.filter((t) => t.source === 'manual').slice(0, MANUAL_TAKES), ...all.filter((t) => t.source === 'auto').slice(0, AUTO_TAKES)]
    const ids = new Set(keep.map((t) => t.id))
    return this.write(all.filter((t) => ids.has(t.id)))
  }

  async remove(id: string): Promise<Take[]> {
    return this.write((await this.list()).filter((t) => t.id !== id))
  }

  private async write(takes: Take[]): Promise<Take[]> {
    await mkdir(dirname(this.file), { recursive: true })
    await writeFile(this.file, JSON.stringify(takes))
    return takes
  }
}
