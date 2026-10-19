import { createWriteStream } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { Readable, Transform } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import type { RenderStatus } from '../../shared/agent'
import type { ExportState } from '../../shared/export'
import { api } from '../api'

const POLL_MS = 2000
const IDLE: ExportState = { phase: 'idle', render: null, progress: 0, file: null, error: null }
const message = (error: unknown) => (error instanceof Error ? error.message : String(error))

export interface ExportDeps {
  token(): Promise<string | null>
  /** The open project's id and title. */
  project(): { id: string; title: string } | null
  /** The folder finished videos go to. */
  folder: string
  onChange(state: ExportState): void
  wait?(ms: number): Promise<void>
}

/** "Founder chat ep 12" → "Founder chat ep 12 2026-10-18 17-05.mp4", safe for Finder. */
export function fileName(title: string, at = new Date()): string {
  const safe = title.replace(/[/:\\?*"<>|]+/g, ' ').replace(/\s+/g, ' ').trim() || 'Clipnera edit'
  const stamp = `${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, '0')}-${String(at.getDate()).padStart(2, '0')} ${String(at.getHours()).padStart(2, '0')}-${String(at.getMinutes()).padStart(2, '0')}`
  return `${safe} ${stamp}.mp4`
}

/**
 * Exports the project: the backend renders the saved edit at full size (brain/server_render.py),
 * this follows it to the end and saves the finished MP4 on the Mac.
 */
export class ExportService {
  private state: ExportState = IDLE
  private following: string | null = null

  constructor(private readonly deps: ExportDeps) {}

  get(): ExportState {
    return this.state
  }

  /** Starts a render of the project as it is saved now. */
  async start(): Promise<void> {
    if (this.state.phase === 'rendering' || this.state.phase === 'downloading') throw new Error('An export is already running')
    const project = this.require()
    this.set({ ...IDLE, phase: 'rendering' })
    try {
      const render = await api.postData<RenderStatus>(`/editor/projects/${project.id}/renders`, {}, await this.auth())
      await this.follow(render)
    } catch (error) {
      this.set({ phase: 'failed', error: message(error) })
    }
  }

  /** Follows a render someone else started (the AI's start_export). */
  async follow(render: RenderStatus): Promise<void> {
    if (this.following === render.id) return
    this.following = render.id
    const project = this.require()
    const wait = this.deps.wait ?? ((ms) => new Promise((r) => setTimeout(r, ms)))
    try {
      let current = render
      this.set({ phase: 'rendering', render: current, error: null, file: null })
      while (current.status === 'queued' || current.status === 'rendering') {
        await wait(POLL_MS)
        current = await api.getData<RenderStatus>(`/editor/projects/${project.id}/renders/${render.id}`, await this.auth())
        this.set({ render: current })
      }
      if (current.status === 'failed' || !current.download_url) throw new Error(current.error ?? 'The render failed')
      this.set({ phase: 'downloading', progress: 0 })
      const file = join(this.deps.folder, fileName(project.title))
      await this.download(current.download_url, file)
      this.set({ phase: 'saved', progress: 1, file })
    } catch (error) {
      this.set({ phase: 'failed', error: message(error) })
    } finally {
      this.following = null
    }
  }

  private async download(url: string, file: string): Promise<void> {
    const response = await fetch(url)
    if (!response.ok || !response.body) throw new Error(`Downloading the video failed (${response.status})`)
    const total = Number(response.headers.get('content-length')) || 0
    let received = 0
    const count = new Transform({
      transform: (chunk: Buffer, _enc, done) => {
        received += chunk.length
        if (total) this.set({ progress: received / total })
        done(null, chunk)
      }
    })
    await mkdir(this.deps.folder, { recursive: true })
    await pipeline(Readable.fromWeb(response.body as import('node:stream/web').ReadableStream), count, createWriteStream(file))
  }

  private require(): { id: string; title: string } {
    const project = this.deps.project()
    if (!project) throw new Error('No project is open')
    return project
  }

  private async auth(): Promise<string> {
    const token = await this.deps.token()
    if (!token) throw new Error('Sign in to export')
    return token
  }

  private set(patch: Partial<ExportState>): void {
    this.state = { ...this.state, ...patch }
    this.deps.onChange(this.state)
  }
}
