import { existsSync } from 'node:fs'
import { mkdir, rename, writeFile } from 'node:fs/promises'
import { basename, join } from 'node:path'
import { MEDIA_SCHEME } from '../../shared/media'

/** The host under clipnera-media:// that serves the cached shelf files. */
export const SHELF_HOST = 'shelf'
const SAFE_NAME = /^[\w.-]+$/

/**
 * Copies of the backend's shelf files (the animated graphics) on this Mac, played through
 * clipnera-media://shelf/<file>. The backend serves them without byte ranges, and a video the
 * viewer can't seek in would only ever show its first frame.
 */
export class ShelfCache {
  constructor(private readonly dir: string) {}

  /** The local file for a cached shelf file, or null. */
  filePath(name: string): string | null {
    const file = join(this.dir, name)
    return SAFE_NAME.test(name) && existsSync(file) ? file : null
  }

  /** `url` fetched once into the cache; returns its clipnera-media:// address. */
  async local(url: string): Promise<string> {
    const name = basename(new URL(url).pathname)
    if (!SAFE_NAME.test(name)) throw new Error(`Unexpected shelf file name: ${name}`)
    const file = join(this.dir, name)
    if (!existsSync(file)) {
      const response = await fetch(url)
      if (!response.ok) throw new Error(`Couldn't download ${name}: ${response.status}`)
      await mkdir(this.dir, { recursive: true })
      // Written aside and moved in, so a half-downloaded file is never served.
      await writeFile(`${file}.part`, Buffer.from(await response.arrayBuffer()))
      await rename(`${file}.part`, file)
    }
    return `${MEDIA_SCHEME}://${SHELF_HOST}/${name}`
  }
}
