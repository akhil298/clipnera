import type { TimelineOp } from '@timeline'
import type { MediaAnalysisResponse } from '../../shared/api'
import type { ProjectSnapshot, ProjectState } from '../../shared/project'
import type { ProjectBackend, UploadFile } from './backend'

const message = (error: unknown) => (error instanceof Error ? error.message : String(error))
const ANALYSIS_POLL_MS = 2500
// Edits come in bursts; read the preview once they settle.
const PREVIEW_DELAY_MS = 300
const working = (a: MediaAnalysisResponse) => a.status === 'pending' || a.status === 'running'

/**
 * The open project. Changes go to the backend one batch at a time, each against the version
 * the last one produced, so edits never race each other. Every change is pushed to the UI.
 */
export class ProjectService {
  private state: ProjectState = { project: null, saving: false, loading: false, error: null, analysis: {}, preview: null, captionStyles: [], looks: [] }
  private poll: ReturnType<typeof setTimeout> | null = null
  private previewTimer: ReturnType<typeof setTimeout> | null = null
  private backend: ProjectBackend | null = null
  private queue: Promise<unknown> = Promise.resolve()
  private readonly listeners = new Set<(state: ProjectState) => void>()

  get(): ProjectState {
    return this.state
  }

  subscribe(listener: (state: ProjectState) => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  async open(backend: ProjectBackend): Promise<ProjectSnapshot | null> {
    this.backend = backend
    this.stopPolling()
    this.set({ project: null, loading: true, error: null, analysis: {}, preview: null, captionStyles: [], looks: [] })
    try {
      const project = await backend.openLatest()
      if (this.backend === backend) {
        this.set({ project, loading: false })
        void this.checkAnalysis()
        this.schedulePreview()
        void backend.captionStyles().then((captionStyles) => this.backend === backend && this.set({ captionStyles })).catch(() => undefined)
        void backend.looks().then((looks) => this.backend === backend && this.set({ looks })).catch(() => undefined)
      }
      return project
    } catch (error) {
      if (this.backend === backend) this.set({ loading: false, error: message(error) })
      return null
    }
  }

  close(): void {
    this.backend = null
    this.stopPolling()
    if (this.previewTimer) clearTimeout(this.previewTimer)
    this.set({ project: null, saving: false, loading: false, error: null, analysis: {}, preview: null, captionStyles: [], looks: [] })
  }

  /**
   * Reads how far the AI has got with each asset, and keeps reading every few seconds while
   * anything is still being understood.
   */
  async checkAnalysis(): Promise<void> {
    this.stopPolling()
    const backend = this.backend
    const project = this.state.project
    if (!backend?.understands || !project) return
    let rows: MediaAnalysisResponse[] = []
    try {
      rows = await backend.analysis(project.id)
    } catch {
      // Try again on the next round.
    }
    if (this.backend !== backend || this.state.project?.id !== project.id) return
    if (rows.length) {
      const before = Object.values(this.state.analysis).filter((a) => a.status === 'ready').length
      this.set({ analysis: Object.fromEntries(rows.map((a) => [a.asset_id, a])) })
      // A newly understood file brings caption words.
      if (rows.filter((a) => a.status === 'ready').length > before) this.schedulePreview()
    }
    if (rows.some(working) || Object.keys(project.timeline.assets).some((id) => !this.state.analysis[id])) {
      this.poll = setTimeout(() => void this.checkAnalysis(), ANALYSIS_POLL_MS)
    }
  }

  async retryAnalysis(assetId: string): Promise<void> {
    const { backend, project } = this.require()
    const row = await backend.retryAnalysis(project.id, assetId)
    this.set({ analysis: { ...this.state.analysis, [assetId]: row } })
    void this.checkAnalysis()
  }

  /** Reads what the export will draw over the picture, shortly after the project last changed. */
  schedulePreview(): void {
    if (this.previewTimer) clearTimeout(this.previewTimer)
    this.previewTimer = setTimeout(() => {
      const backend = this.backend
      const project = this.state.project
      if (!backend || !project) return
      void backend
        .preview(project.id, project.timeline, project.version)
        .then((preview) => this.backend === backend && this.state.project?.id === project.id && this.set({ preview }))
        .catch(() => undefined)
    }, PREVIEW_DELAY_MS)
  }

  private stopPolling(): void {
    if (this.poll) clearTimeout(this.poll)
    this.poll = null
  }

  apply(ops: TimelineOp[]): Promise<ProjectSnapshot> {
    return this.change((backend, project) => backend.apply(project.id, project.version, ops))
  }

  undo(): Promise<ProjectSnapshot> {
    return this.change((backend, project) => backend.undo(project.id))
  }

  redo(): Promise<ProjectSnapshot> {
    return this.change((backend, project) => backend.redo(project.id))
  }

  /** Re-reads the project, e.g. after the AI changed it on the server. */
  refresh(): Promise<ProjectSnapshot> {
    return this.run(async (backend, project) => {
      const fresh = await backend.get(project.id)
      this.set({ project: fresh, error: null })
      this.schedulePreview()
      return fresh
    })
  }

  style() {
    return this.require().backend.style()
  }

  forgetStyle(key: string) {
    return this.require().backend.forgetStyle(key)
  }

  sounds(query: string) {
    const { backend } = this.require()
    return backend.sounds(query)
  }

  graphics() {
    return this.require().backend.graphics()
  }

  upload(file: UploadFile, onProgress: (fraction: number) => void): Promise<string> {
    const { backend, project } = this.require()
    return backend.upload(project.id, file, onProgress)
  }

  private change(send: (backend: ProjectBackend, project: ProjectSnapshot) => Promise<Pick<ProjectSnapshot, 'version' | 'timeline'>>) {
    return this.run(async (backend, project) => {
      this.set({ saving: true })
      try {
        const next = { ...project, ...(await send(backend, project)) }
        this.set({ project: next, saving: false, error: null })
        this.schedulePreview()
        // New footage starts being understood on the backend; follow it.
        if (Object.keys(next.timeline.assets).some((id) => !this.state.analysis[id])) void this.checkAnalysis()
        return next
      } catch (error) {
        // Show the project as the backend has it, so the UI never keeps an edit that didn't land.
        const fresh = await backend.get(project.id).catch(() => project)
        this.set({ project: fresh, saving: false, error: message(error) })
        throw error
      }
    })
  }

  /** Runs after everything queued before it, against the project as it is by then. */
  private run<T>(task: (backend: ProjectBackend, project: ProjectSnapshot) => Promise<T>): Promise<T> {
    const next = this.queue.then(() => {
      const { backend, project } = this.require()
      return task(backend, project)
    })
    this.queue = next.catch(() => undefined)
    return next
  }

  private require(): { backend: ProjectBackend; project: ProjectSnapshot } {
    const project = this.state.project
    if (!this.backend || !project) throw new Error('No project is open')
    return { backend: this.backend, project }
  }

  private set(patch: Partial<ProjectState>): void {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((listener) => listener(this.state))
  }
}
