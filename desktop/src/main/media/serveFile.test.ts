import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { parseRange, serveFile } from './serveFile'

const file = join(mkdtempSync(join(tmpdir(), 'clipnera-serve-')), 'clip.mp4')
writeFileSync(file, '0123456789')
const get = (range?: string) => serveFile(file, new Request('clipnera-media://x/proxy.mp4', { headers: range ? { range } : {} }))

describe('parseRange', () => {
  it('reads the range forms players send', () => {
    expect(parseRange('bytes=0-', 10)).toEqual({ start: 0, end: 9 })
    expect(parseRange('bytes=2-4', 10)).toEqual({ start: 2, end: 4 })
    expect(parseRange('bytes=-3', 10)).toEqual({ start: 7, end: 9 })
    expect(parseRange('bytes=5-100', 10)).toEqual({ start: 5, end: 9 })
  })

  it('refuses ranges outside the file or malformed', () => {
    expect(parseRange('bytes=10-', 10)).toBeNull()
    expect(parseRange('bytes=4-2', 10)).toBeNull()
    expect(parseRange('bytes=-', 10)).toBeNull()
    expect(parseRange('items=0-1', 10)).toBeNull()
  })
})

describe('serveFile', () => {
  it('serves the whole file with its type', async () => {
    const response = await get()
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('video/mp4')
    expect(response.headers.get('accept-ranges')).toBe('bytes')
    expect(await response.text()).toBe('0123456789')
  })

  it('serves a byte range for seeking', async () => {
    const response = await get('bytes=2-5')
    expect(response.status).toBe(206)
    expect(response.headers.get('content-range')).toBe('bytes 2-5/10')
    expect(response.headers.get('content-length')).toBe('4')
    expect(await response.text()).toBe('2345')
  })

  it('answers 416 for a range past the end and 404 for a missing file', async () => {
    expect((await get('bytes=50-')).status).toBe(416)
    expect((await serveFile('/nope.mp4', new Request('clipnera-media://x/y'))).status).toBe(404)
  })
})
