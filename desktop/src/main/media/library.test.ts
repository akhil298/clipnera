import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { Asset } from '@timeline'
import type { MediaItem, ProbeResult } from '../../shared/media'
import { EngineError, type Engine, type EngineJob, type RequestOptions } from '../engine/client'
import { MediaLibrary, type MediaProject } from './library'

const VIDEO: ProbeResult = { durationSeconds: 4, fileSize: 1, hasVideo: true, hasAudio: true, width: 1920, height: 1080, fps: 30 }
const PROXY: ProbeResult = { ...VIDEO, width: 1280, height: 720 }
const AUDIO: ProbeResult = { durationSeconds: 2, fileSize: 1, hasVideo: false, hasAudio: true }

/** Answers each request when the test says so, to step through the library's states. */
class FakeEngine implements Engine {
  calls: { method: string; params: Record<string, unknown>; resolve(v: unknown): void; reject(e: Error): void; options: RequestOptions; cancelled: boolean; done?: boolean }[] = []

  request<T>(method: string, params: Record<string, unknown> = {}, options: RequestOptions = {}): EngineJob<T> {
    let resolve!: (v: unknown) => void
    let reject!: (e: Error) => void
    const result = new Promise<T>((res, rej) => ((resolve = res as (v: unknown) => void), (reject = rej)))
    const call = { method, params, resolve, reject, options, cancelled: false }
    this.calls.push(call)
    // Editing copies are written by the engine; make a file so the library can measure it.
    if (method === 'proxy') {
      mkdirSync(join(String(params.output), '..'), { recursive: true })
      writeFileSync(String(params.output), 'copy')
    }
    return { id: this.calls.length, result, cancel: () => ((call.cancelled = true), reject(new EngineError('CANCELLED', 'Cancelled'))) }
  }

  next(method: string) {
    const call = this.calls.find((c) => c.method === method && !c.done)
    if (!call) throw new Error(`no pending ${method}`)
    call.done = true
    return call
  }
}

class FakeProject implements MediaProject {
  assets: Asset[] = []
  uploads: string[] = []
  used = new Set<string>()
  fps = () => 30
  hasAsset = (id: string) => this.assets.some((a) => a.id === id)
  usesAsset = (id: string) => this.used.has(id)
  async upload(file: { filename: string }, onProgress: (f: number) => void) {
    this.uploads.push(file.filename)
    onProgress(1)
    return `editor/u/p/${file.filename}`
  }
  async addAsset(asset: Asset) {
    this.assets.push(asset)
  }
}

const flush = async () => {
  for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0))
}

async function setUp() {
  const engine = new FakeEngine()
  const cache = mkdtempSync(join(tmpdir(), 'clipnera-cache-'))
  const store = join(cache, 'project', 'media.json')
  const changes: MediaItem[][] = []
  const project = new FakeProject()
  const library = new MediaLibrary(engine, cache, (items) => changes.push(items))
  await library.open(project, store)
  return { engine, cache, store, library, changes, project }
}

describe('MediaLibrary', () => {
  it('reads, thumbnails, prepares and adds a video to the project', async () => {
    const { engine, library, project } = await setUp()
    const [item] = library.import(['/footage/a.mov'])
    expect(item).toMatchObject({ name: 'a.mov', status: 'reading' })

    engine.next('probe').resolve(VIDEO)
    await flush()
    expect(engine.next('thumbnail').params).toMatchObject({ path: '/footage/a.mov', atSeconds: 1, maxSize: 320 })
    engine.calls.at(-1)!.resolve({})
    await flush()
    expect(library.list()[0]).toMatchObject({ status: 'preparing', thumbnail: `clipnera-media://${item.id}/thumb.jpg` })

    const proxy = engine.next('proxy')
    expect(proxy.params).toMatchObject({ audioOnly: false })
    proxy.options.onProgress?.(0.5)
    expect(library.list()[0].progress).toBe(0.5)
    proxy.resolve({})
    await flush()
    engine.next('probe').resolve(PROXY)
    await flush()

    expect(library.list()[0]).toMatchObject({ status: 'ready', kind: 'video', progress: 1 })
    expect(project.uploads).toEqual(['a.mp4'])
    // Then it looks for subtitles already in the picture.
    engine.next('textscan').resolve({ share: 0.25, examples: ["We'll have babies"] })
    await flush()
    expect(library.list()[0].onScreenText).toEqual({ share: 0.25, examples: ["We'll have babies"] })
    // The asset describes the uploaded 720p copy, its length in timeline frames.
    expect(project.assets).toEqual([{ id: item.id, kind: 'video', key: 'editor/u/p/a.mp4', proxy: null, frames: 120, width: 1280, height: 720, has_audio: true }])
  })

  it('gives audio an AAC copy and adds it as an audio asset', async () => {
    const { engine, library, project } = await setUp()
    library.import(['/footage/voice.wav'])
    engine.next('probe').resolve(AUDIO)
    await flush()
    expect(engine.next('proxy').params).toMatchObject({ audioOnly: true })
    engine.calls.at(-1)!.resolve({})
    await flush()
    expect(library.list()[0]).toMatchObject({ kind: 'audio', status: 'ready' })
    expect(project.uploads).toEqual(['voice.m4a'])
    expect(project.assets[0]).toMatchObject({ kind: 'audio', frames: 60, width: null, has_audio: true })
  })

  it('shows why a file failed', async () => {
    const { engine, library } = await setUp()
    library.import(['/footage/clip.webm'])
    engine.next('probe').reject(new EngineError('UNSUPPORTED', "macOS can't open this file format."))
    await flush()
    expect(library.list()[0]).toMatchObject({ status: 'failed', error: "macOS can't open this file format." })
  })

  it('skips files that are already in the library', async () => {
    const { library } = await setUp()
    library.import(['/a.mov', '/a.mov'])
    expect(library.import(['/a.mov', '/b.mov']).map((i) => i.name)).toEqual(['b.mov'])
    expect(library.list()).toHaveLength(2)
  })

  it('makes editing copies one at a time', async () => {
    const { engine, library } = await setUp()
    library.import(['/a.mov', '/b.mov'])
    for (let i = 0; i < 2; i++) {
      engine.next('probe').resolve(VIDEO)
      await flush()
      engine.next('thumbnail').resolve({})
      await flush()
    }
    expect(engine.calls.filter((c) => c.method === 'proxy')).toHaveLength(1)
    engine.next('proxy').resolve({})
    await flush()
    expect(engine.calls.filter((c) => c.method === 'proxy')).toHaveLength(2)
  })

  it('keeps the list per project and finishes half-done files after a restart', async () => {
    const { engine, library, store, project, cache } = await setUp()
    library.import(['/a.mov'])
    await flush()
    expect(JSON.parse(readFileSync(store, 'utf8'))).toHaveLength(1)

    const again = new MediaLibrary(engine, cache, () => undefined)
    await again.open(project, store)
    expect(again.list()[0]).toMatchObject({ name: 'a.mov', status: 'reading' })
    expect(engine.calls.filter((c) => c.method === 'probe')).toHaveLength(2)
  })

  it('removing cancels its work and deletes cached copies, never the original', async () => {
    const { engine, library, cache } = await setUp()
    const original = join(mkdtempSync(join(tmpdir(), 'orig-')), 'a.mov')
    writeFileSync(original, 'video')
    const [item] = library.import([original])
    mkdirSync(join(cache, item.id))
    writeFileSync(join(cache, item.id, 'thumb.jpg'), 'jpg')

    const probe = engine.calls[0]
    await library.remove(item.id)
    await flush()

    expect(probe.cancelled).toBe(true)
    expect(library.list()).toEqual([])
    expect(existsSync(join(cache, item.id))).toBe(false)
    expect(existsSync(original)).toBe(true)
  })

  it("won't remove a file that is on the timeline", async () => {
    const { library, project } = await setUp()
    const [item] = library.import(['/a.mov'])
    project.used.add(item.id)
    await expect(library.remove(item.id)).rejects.toThrow('Remove it from the timeline first')
  })

  it('serves only known cache files, and originals only for audio', async () => {
    const { engine, library, cache } = await setUp()
    const [video, audio] = library.import(['/a.mov', '/voice.wav'])
    expect(library.filePath(video.id, 'thumb.jpg')).toBe(join(cache, video.id, 'thumb.jpg'))
    expect(library.filePath(video.id, 'proxy.m4a')).toBe(join(cache, video.id, 'proxy.m4a'))
    expect(library.filePath(video.id, '../../etc/passwd')).toBeNull()
    expect(library.filePath('someone-else', 'thumb.jpg')).toBeNull()

    engine.next('probe').resolve(VIDEO)
    engine.next('probe').resolve(AUDIO)
    await flush()
    expect(library.filePath(audio.id, 'source')).toBe('/voice.wav')
    expect(library.filePath(video.id, 'source')).toBeNull()
  })
})
