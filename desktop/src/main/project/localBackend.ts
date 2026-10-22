import { randomUUID } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { applyOps, normalise, type Timeline, type TimelineOp } from '@timeline'
import { textKind } from './preview'
import type { ProjectPreview } from '../../shared/api'
import type { ProjectSnapshot } from '../../shared/project'
import type { ProjectBackend } from './backend'

const UNDO_LIMIT = 100

interface Saved {
  project: ProjectSnapshot
  undo: Timeline[]
  redo: Timeline[]
}

/** A new project as the backend makes one: 16:9 at 30 fps with one video track. */
export function emptyTimeline(): Timeline {
  return normalise({ version: 1, fps: 30, width: 1920, height: 1080, tracks: [{ id: 'v1', kind: 'video', items: [] }] })
}

/**
 * Preview mode's project, kept in one file on this Mac. Edits go through the same applyOps
 * the backend's fixtures check, so a preview edit behaves exactly like a real one.
 */
export class LocalProjectBackend implements ProjectBackend {
  readonly understands = false
  private saved: Saved | null = null

  constructor(private readonly file: string) {}

  async openLatest(): Promise<ProjectSnapshot> {
    return (await this.load()).project
  }

  async get(): Promise<ProjectSnapshot> {
    return (await this.load()).project
  }

  async apply(_id: string, _baseVersion: number, ops: TimelineOp[]) {
    const saved = await this.load()
    const timeline = applyOps(saved.project.timeline, ops)
    saved.undo = [...saved.undo, saved.project.timeline].slice(-UNDO_LIMIT)
    saved.redo = []
    return this.commit(saved, timeline)
  }

  async undo() {
    const saved = await this.load()
    const previous = saved.undo.pop()
    if (!previous) throw new Error('Nothing to undo')
    saved.redo.push(saved.project.timeline)
    return this.commit(saved, previous)
  }

  async redo() {
    const saved = await this.load()
    const next = saved.redo.pop()
    if (!next) throw new Error('Nothing to redo')
    saved.undo.push(saved.project.timeline)
    return this.commit(saved, next)
  }

  /** Preview footage stays on this Mac, so there is nothing to upload. */
  async upload(id: string, file: { filename: string }): Promise<string> {
    return `editor/local/${id}/${randomUUID()}-${file.filename}`
  }

  /** Understanding footage needs the backend; preview mode has none. */
  async analysis(): Promise<[]> {
    return []
  }

  async retryAnalysis(): Promise<never> {
    throw new Error('Sign in to let the AI look at your footage')
  }

  /** Titles only: captions need the backend's transcript. */
  async preview(_id: string, timeline: Timeline, version: number): Promise<ProjectPreview> {
    const texts = timeline.tracks
      .filter((t) => !t.hidden)
      .flatMap((t) => t.items)
      .flatMap((i) => (i.type === 'text' ? [{ kind: textKind(i), text: i.text, at: i.at / timeline.fps, dur: i.dur / timeline.fps }] : []))
      .sort((a, b) => a.at - b.at)
    return { version, look: timeline.look, caption_style: null, caption_look: null, words: [], texts, sounds: [] }
  }

  async captionStyles(): Promise<[]> {
    return []
  }

  /** Style memory lives on the backend. */
  async style(): Promise<[]> {
    return []
  }

  async forgetStyle(): Promise<[]> {
    return []
  }

  /** The looks come from the backend's renderer. */
  async looks(): Promise<[]> {
    return []
  }

  /** The sound library lives on the backend. */
  async music(): Promise<[]> {
    return []
  }

  async addMusic(): Promise<never> {
    throw new Error('The music shelf needs the Clipnera backend; sign in to use it')
  }

  /** The AI's tools work on the Clipnera backend; here the person's Claude has the editor's commands only. */
  async agentTools(): Promise<[]> {
    return []
  }

  async agentTool(): Promise<never> {
    throw new Error('The AI’s editing tools need the Clipnera backend; sign in to use them')
  }

  async broll(): Promise<[]> {
    return []
  }

  async addBroll(): Promise<never> {
    throw new Error('B-roll needs the Clipnera backend; sign in to use it')
  }

  async graphics(): Promise<[]> {
    return []
  }

  async sounds(): Promise<[]> {
    return []
  }

  private async commit(saved: Saved, timeline: Timeline) {
    saved.project = { ...saved.project, timeline, version: saved.project.version + 1 }
    await mkdir(dirname(this.file), { recursive: true })
    await writeFile(this.file, JSON.stringify(saved))
    return { version: saved.project.version, timeline }
  }

  private async load(): Promise<Saved> {
    if (this.saved) return this.saved
    try {
      this.saved = JSON.parse(await readFile(this.file, 'utf8')) as Saved
    } catch {
      this.saved = { project: { id: 'preview', title: 'Preview project', version: 0, timeline: emptyTimeline(), assetUrls: {} }, undo: [], redo: [] }
    }
    return this.saved
  }
}
