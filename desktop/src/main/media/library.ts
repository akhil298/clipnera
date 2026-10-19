import { randomUUID } from 'node:crypto'
import { mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { basename, dirname, extname, join } from 'node:path'
import type { Asset } from '@timeline'
import { CACHE_FILES, MEDIA_SCHEME, SOURCE_FILE, type MediaItem, type ProbeResult } from '../../shared/media'
import type { UploadFile } from '../project/backend'
import { EngineError, type Engine, type EngineJob } from '../engine/client'

const THUMBNAIL_SIZE = 320
// Frames sampled to look for subtitles already burned into the picture.
const TEXT_SAMPLES = 16

const reason = (error: unknown) => (error instanceof Error ? error.message : String(error))

/** What the library needs from the open project. */
export interface MediaProject {
  fps(): number
  upload(file: UploadFile, onProgress: (fraction: number) => void): Promise<string>
  addAsset(asset: Asset): Promise<void>
  hasAsset(assetId: string): boolean
  /** True when an item on the timeline uses this asset. */
  usesAsset(assetId: string): boolean
}

/**
 * The open project's footage. Each file is read, gets a thumbnail and a small editing copy
 * (1080p H.264, or AAC for audio), and that copy is uploaded and added to the project as an
 * asset — the item's id is the asset id. Copies are made one at a time so a big import
 * doesn't swamp the Mac. Originals are never changed or deleted. The list is saved per project.
 */
export class MediaLibrary {
  private items: MediaItem[] = []
  private readonly jobs = new Map<string, EngineJob<unknown>>()
  private proxyQueue: Promise<void> = Promise.resolve()
  private project: MediaProject | null = null
  private storeFile: string | null = null
  private saving: Promise<void> = Promise.resolve()

  constructor(
    private readonly engine: Engine,
    private readonly cacheDir: string,
    private readonly onChange: (items: MediaItem[]) => void
  ) {}

  list(): MediaItem[] {
    return this.items
  }

  /** Loads a project's saved list and finishes anything an earlier run left half done. */
  async open(project: MediaProject, storeFile: string): Promise<void> {
    this.close()
    this.project = project
    this.storeFile = storeFile
    let saved: MediaItem[] = []
    try {
      saved = JSON.parse(await readFile(storeFile, 'utf8')) as MediaItem[]
    } catch {
      // No list yet for this project.
    }
    this.items = saved.map((item) => (item.status === 'ready' || item.status === 'failed' ? item : { ...item, status: 'reading', progress: 0 }))
    this.emit()
    for (const item of this.items) if (item.status === 'reading') void this.prepare(item.id)
  }

  close(): void {
    for (const job of this.jobs.values()) job.cancel()
    this.jobs.clear()
    this.project = null
    this.storeFile = null
    this.items = []
    this.emit()
  }

  /** Adds files not already in the library; returns the new items. */
  import(paths: string[]): MediaItem[] {
    if (!this.project) throw new Error('No project is open')
    const known = new Set(this.items.map((i) => i.path))
    const added = [...new Set(paths)]
      .filter((path) => !known.has(path))
      .map((path): MediaItem => ({ id: randomUUID(), path, name: basename(path), kind: 'unknown', status: 'reading', progress: 0 }))
    if (added.length === 0) return []
    this.items = [...this.items, ...added]
    this.save()
    for (const item of added) void this.prepare(item.id)
    return added
  }

  /** Takes a file out of the project's media and drops its cached copies. The original stays where it is. */
  async remove(id: string): Promise<void> {
    if (!this.find(id)) return
    if (this.project?.usesAsset(id)) throw new Error('This file is on the timeline. Remove it from the timeline first.')
    this.jobs.get(id)?.cancel()
    this.items = this.items.filter((i) => i.id !== id)
    this.save()
    await rm(join(this.cacheDir, id), { recursive: true, force: true })
  }

  /**
   * The file behind clipnera-media://<id>/<file>: a cached thumbnail or editing copy, or an audio
   * item's original. Anything else, or an id not in the library, is refused.
   */
  filePath(id: string, file: string): string | null {
    const item = this.find(id)
    if (!item) return null
    if (file === SOURCE_FILE) return item.kind === 'audio' ? item.path : null
    return (Object.values(CACHE_FILES) as string[]).includes(file) ? join(this.cacheDir, id, file) : null
  }

  private async prepare(id: string): Promise<void> {
    const item = this.find(id)
    if (!item) return
    try {
      const info = await this.run<ProbeResult>(id, 'probe', { path: item.path })
      const audioOnly = !info.hasVideo
      if (!audioOnly) {
        const output = join(this.cacheDir, id, CACHE_FILES.thumbnail)
        await this.run(id, 'thumbnail', { path: item.path, atSeconds: Math.min(1, info.durationSeconds / 2), maxSize: THUMBNAIL_SIZE, output })
      }
      this.update(id, {
        kind: audioOnly ? 'audio' : 'video',
        info,
        status: 'preparing',
        progress: 0,
        thumbnail: audioOnly ? undefined : `${MEDIA_SCHEME}://${id}/${CACHE_FILES.thumbnail}`
      })

      const proxy = join(this.cacheDir, id, audioOnly ? CACHE_FILES.audioProxy : CACHE_FILES.proxy)
      await this.queueProxy(id, proxy, audioOnly)
      await this.addToProject(id, info, proxy, audioOnly)
      this.update(id, { status: 'ready', progress: 1 })
      if (!audioOnly) void this.scanForText(id, proxy)
    } catch (error) {
      // A removed item's jobs are cancelled; there is nothing left to report.
      if (error instanceof EngineError && error.code === 'CANCELLED') return
      this.update(id, { status: 'failed', error: reason(error) })
    }
  }

  /** Looks for words already on screen (burned-in subtitles), so captions aren't laid over them. */
  private async scanForText(id: string, proxy: string): Promise<void> {
    try {
      const found = await this.run<{ share: number; examples: string[] }>(id, 'textscan', { path: proxy, samples: TEXT_SAMPLES })
      this.update(id, { onScreenText: { share: found.share, examples: found.examples } })
    } catch {
      // Only a hint: without it captions still work.
    }
  }

  /** Uploads the editing copy and adds it to the project as an asset. */
  private async addToProject(id: string, info: ProbeResult, proxy: string, audioOnly: boolean): Promise<void> {
    const project = this.project
    const item = this.find(id)
    if (!project || !item || project.hasAsset(id)) return
    this.update(id, { status: 'uploading', progress: 0 })
    // The asset describes the stored copy, which may be smaller than the original.
    const copy = audioOnly ? info : await this.run<ProbeResult>(id, 'probe', { path: proxy })
    const name = `${basename(item.name, extname(item.name))}${audioOnly ? '.m4a' : '.mp4'}`
    const key = await project.upload(
      { path: proxy, filename: name, contentType: audioOnly ? 'audio/mp4' : 'video/mp4', size: (await stat(proxy)).size },
      (progress) => this.update(id, { progress })
    )
    await project.addAsset({
      id,
      kind: audioOnly ? 'audio' : 'video',
      key,
      proxy: null,
      frames: Math.max(1, Math.round(info.durationSeconds * project.fps())),
      width: audioOnly ? null : (copy.width ?? null),
      height: audioOnly ? null : (copy.height ?? null),
      has_audio: info.hasAudio
    })
  }

  private queueProxy(id: string, output: string, audioOnly: boolean): Promise<void> {
    const run = this.proxyQueue.then(async () => {
      if (!this.find(id)) return
      await this.run(id, 'proxy', { path: this.find(id)?.path, output, audioOnly }, (progress) => this.update(id, { progress }))
    })
    this.proxyQueue = run.catch(() => undefined)
    return run
  }

  private async run<T>(id: string, method: string, params: Record<string, unknown>, onProgress?: (fraction: number) => void): Promise<T> {
    const job = this.engine.request<T>(method, params, { onProgress })
    this.jobs.set(id, job)
    try {
      return await job.result
    } finally {
      if (this.jobs.get(id) === job) this.jobs.delete(id)
    }
  }

  private find(id: string): MediaItem | undefined {
    return this.items.find((i) => i.id === id)
  }

  private update(id: string, patch: Partial<MediaItem>): void {
    if (!this.find(id)) return
    this.items = this.items.map((i) => (i.id === id ? { ...i, ...patch } : i))
    // Progress ticks only refresh the UI; everything else is worth keeping.
    if (Object.keys(patch).some((key) => key !== 'progress')) this.save()
    else this.emit()
  }

  private save(): void {
    this.emit()
    const file = this.storeFile
    if (!file) return
    const items = JSON.stringify(this.items)
    // In order, so an older list never lands after a newer one.
    this.saving = this.saving.then(() => mkdir(dirname(file), { recursive: true })).then(() => writeFile(file, items)).catch(() => undefined)
  }

  private emit(): void {
    this.onChange(this.items)
  }
}
