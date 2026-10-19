import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { applyOps, normalise, type Timeline, type TimelineOp } from '@timeline'
import type { MediaAnalysisResponse } from '../../shared/api'
import type { ProjectSnapshot } from '../../shared/project'
import type { ProjectBackend } from './backend'
import { ProjectService } from './service'

const ASSET = { id: 'a1', kind: 'video' as const, key: 'editor/u/p/a.mp4', proxy: null, frames: 90, width: 1280, height: 720, has_audio: true }

class FakeBackend implements ProjectBackend {
  understands = true
  version = 0
  timeline: Timeline = normalise({ fps: 30, tracks: [{ id: 'v1', kind: 'video', items: [] }] })
  sent: number[] = []
  rows: MediaAnalysisResponse[][] = []
  fail = false

  snapshot = (): ProjectSnapshot => ({ id: 'p1', title: 'Project', version: this.version, timeline: this.timeline, assetUrls: {} })
  openLatest = async () => this.snapshot()
  get = async () => this.snapshot()
  async apply(_id: string, base: number, ops: TimelineOp[]) {
    this.sent.push(base)
    await new Promise((r) => setTimeout(r, 5))
    if (this.fail) throw new Error('The backend said no')
    this.timeline = applyOps(this.timeline, ops)
    return { version: ++this.version, timeline: this.timeline }
  }
  undo = async () => ({ version: ++this.version, timeline: this.timeline })
  redo = this.undo
  upload = async () => 'editor/u/p/a.mp4'
  analysis = async () => this.rows.shift() ?? []
  retryAnalysis = async () => ({ asset_id: 'a1', status: 'pending' as const, stage: null, findings: null, error: null, updated_at: '' })
  previews = 0
  preview = async (_id: string, _t: Timeline, version: number) => (this.previews++, { version, look: 'natural', caption_style: null, caption_look: null, words: [], texts: [], sounds: [] })
  captionStyles = async () => []
  sounds = async () => []
  graphics = async () => []
  looks = async () => []
  style = async () => []
  forgetStyle = async () => []
}

const row = (status: MediaAnalysisResponse['status']): MediaAnalysisResponse => ({ asset_id: 'a1', status, stage: status === 'running' ? 'transcript' : null, findings: null, error: null, updated_at: '' })

describe('ProjectService', () => {
  beforeEach(() => vi.useRealTimers())
  afterEach(() => vi.useRealTimers())

  it('sends edits one at a time, each against the version before it', async () => {
    const backend = new FakeBackend()
    const service = new ProjectService()
    await service.open(backend)
    await Promise.all([
      service.apply([{ op: 'add_asset', asset: ASSET }]),
      service.apply([{ op: 'add_track', id: 't1', kind: 'text' }]),
      service.apply([{ op: 'add_track', id: 't2', kind: 'text' }])
    ])
    expect(backend.sent).toEqual([0, 1, 2])
    expect(service.get().project?.version).toBe(3)
  })

  it("shows the backend's copy and the reason when an edit is refused", async () => {
    const backend = new FakeBackend()
    const service = new ProjectService()
    await service.open(backend)
    backend.fail = true
    await expect(service.apply([{ op: 'add_asset', asset: ASSET }])).rejects.toThrow('The backend said no')
    expect(service.get()).toMatchObject({ saving: false, error: 'The backend said no' })
    expect(service.get().project?.timeline.assets).toEqual({})
  })

  it('follows the AI understanding new footage until it is done', async () => {
    vi.useFakeTimers()
    const backend = new FakeBackend()
    backend.rows = [[], [row('pending')], [row('running')], [row('ready')]]
    const service = new ProjectService()
    await service.open(backend)
    const applying = service.apply([{ op: 'add_asset', asset: ASSET }])
    await vi.advanceTimersByTimeAsync(10)
    await applying
    // New footage is checked straight away, then every 2.5 s while it's being worked on.
    expect(service.get().analysis.a1?.status).toBe('pending')
    for (const status of ['running', 'ready']) {
      await vi.advanceTimersByTimeAsync(2500)
      expect(service.get().analysis.a1?.status).toBe(status)
    }
    // Done: no more polling.
    await vi.advanceTimersByTimeAsync(10_000)
    expect(backend.rows).toEqual([])
  })

  it('reads the preview once after a burst of edits', async () => {
    vi.useFakeTimers()
    const backend = new FakeBackend()
    const service = new ProjectService()
    await service.open(backend)
    await vi.advanceTimersByTimeAsync(400)
    backend.previews = 0
    const edits = [1, 2, 3].map((n) => service.apply([{ op: 'add_track', id: `t${n}`, kind: 'text' }]))
    await vi.advanceTimersByTimeAsync(50)
    await Promise.all(edits)
    await vi.advanceTimersByTimeAsync(400)
    expect(backend.previews).toBe(1)
    expect(service.get().preview?.version).toBe(3)
  })

  it('never polls in preview mode', async () => {
    vi.useFakeTimers()
    const backend = new FakeBackend()
    backend.understands = false
    const spy = vi.spyOn(backend, 'analysis')
    const service = new ProjectService()
    await service.open(backend)
    await vi.advanceTimersByTimeAsync(10_000)
    expect(spy).not.toHaveBeenCalled()
  })
})
