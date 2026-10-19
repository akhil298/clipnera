import { existsSync, mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import type { ProbeResult } from '../../shared/media'
import { hasFfmpeg, makeTestMedia } from '../testMedia'
import { EngineClient, EngineError } from './client'

const BINARY = join(__dirname, '../../../engine/.build/release/clipnera-engine')

describe.skipIf(!hasFfmpeg)('clipnera-engine', () => {
  let engine: EngineClient
  let files: ReturnType<typeof makeTestMedia>
  const out = mkdtempSync(join(tmpdir(), 'clipnera-out-'))

  beforeAll(() => {
    engine = new EngineClient(BINARY)
    files = makeTestMedia()
  }, 60_000)
  afterAll(() => engine.dispose())

  it('answers ping', async () => {
    expect(await engine.request('ping').result).toEqual({ version: '0.1.0' })
  })

  it('probes video and audio', async () => {
    const video = await engine.request<ProbeResult>('probe', { path: files.video }).result
    expect(video).toMatchObject({ hasVideo: true, hasAudio: true, width: 1920, height: 1080, fps: 30, videoCodec: 'avc1', audioCodec: 'aac' })
    expect(video.durationSeconds).toBeCloseTo(3, 0)

    const audio = await engine.request<ProbeResult>('probe', { path: files.audio }).result
    expect(audio).toMatchObject({ hasVideo: false, hasAudio: true, audioChannels: 1 })
  })

  it('explains files it cannot open', async () => {
    await expect(engine.request('probe', { path: files.webm }).result).rejects.toMatchObject({ code: 'UNSUPPORTED', message: "macOS can't open this file format." })
    await expect(engine.request('probe', { path: '/nope/missing.mp4' }).result).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(engine.request('nope').result).rejects.toMatchObject({ code: 'UNKNOWN_METHOD' })
  })

  it('writes a JPEG thumbnail at the requested size', async () => {
    const output = join(out, 'a', 'thumb.jpg')
    expect(await engine.request('thumbnail', { path: files.video, atSeconds: 1, maxSize: 320, output }).result).toEqual({ path: output, width: 320, height: 180 })
    expect(readFileSync(output).subarray(0, 2)).toEqual(Buffer.from([0xff, 0xd8]))
  })

  it('makes a 1080p editing copy and reports progress', async () => {
    const output = join(out, 'proxy.mp4')
    const progress: number[] = []
    await engine.request('proxy', { path: files.video, output }, { onProgress: (f) => progress.push(f) }).result
    expect(existsSync(output)).toBe(true)
    expect(progress.at(-1)).toBe(1)
    const probe = await engine.request<ProbeResult>('probe', { path: output }).result
    expect(probe).toMatchObject({ width: 1920, height: 1080, hasAudio: true })
  }, 60_000)

  it('cancels a running job and leaves no partial file', async () => {
    const output = join(out, 'cancelled.mp4')
    const job = engine.request('proxy', { path: files.long, output })
    setTimeout(() => job.cancel(), 300)
    await expect(job.result).rejects.toMatchObject({ code: 'CANCELLED' })
    expect(existsSync(output)).toBe(false)
  }, 60_000)

  it('runs requests side by side', async () => {
    const [a, b] = await Promise.all([engine.request('ping').result, engine.request<ProbeResult>('probe', { path: files.audio }).result])
    expect(a).toEqual({ version: '0.1.0' })
    expect(b.hasAudio).toBe(true)
  })
})

describe('EngineClient failures', () => {
  it('fails requests when the engine cannot start', async () => {
    const engine = new EngineClient('/nope/clipnera-engine')
    const error = await engine.request('ping').result.catch((e: unknown) => e)
    expect(error).toBeInstanceOf(EngineError)
    expect((error as EngineError).code).toBe('ENGINE_EXITED')
  })

  it('fails requests in flight when the engine exits, then starts it again', async () => {
    const engine = new EngineClient('/usr/bin/true')
    await expect(engine.request('ping').result).rejects.toMatchObject({ code: 'ENGINE_EXITED' })
    await expect(engine.request('ping').result).rejects.toMatchObject({ code: 'ENGINE_EXITED' })
  })
})
