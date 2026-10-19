import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { extname } from 'node:path'
import { Readable } from 'node:stream'

const TYPES: Record<string, string> = {
  '.jpg': 'image/jpeg',
  '.mp4': 'video/mp4',
  '.mov': 'video/quicktime',
  '.m4v': 'video/mp4',
  '.mp3': 'audio/mpeg',
  '.m4a': 'audio/mp4',
  '.aac': 'audio/aac',
  '.wav': 'audio/wav',
  '.aif': 'audio/aiff',
  '.aiff': 'audio/aiff',
  '.flac': 'audio/flac',
  '.caf': 'audio/x-caf'
}

/** "bytes=start-end" → an inclusive range inside the file, or null when it can't be served. */
export function parseRange(header: string, size: number): { start: number; end: number } | null {
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim())
  if (!match || (match[1] === '' && match[2] === '')) return null
  let start: number
  let end: number
  if (match[1] === '') {
    // "bytes=-500": the last 500 bytes.
    start = Math.max(0, size - Number(match[2]))
    end = size - 1
  } else {
    start = Number(match[1])
    end = match[2] === '' ? size - 1 : Math.min(Number(match[2]), size - 1)
  }
  return start <= end && start < size ? { start, end } : null
}

/** Serves a file, with byte ranges so the video player can seek without reading it all. */
export async function serveFile(path: string, request: Request): Promise<Response> {
  let size: number
  try {
    size = (await stat(path)).size
  } catch {
    return new Response('Not found', { status: 404 })
  }
  // CORS lets the viewer draw a video into WebGL (the graphics layer); only the app's own window can
  // reach this scheme at all.
  const headers: Record<string, string> = {
    'Content-Type': TYPES[extname(path).toLowerCase()] ?? 'application/octet-stream', 'Accept-Ranges': 'bytes', 'Access-Control-Allow-Origin': '*'
  }
  const body = (start: number, end: number) => Readable.toWeb(createReadStream(path, { start, end })) as ReadableStream

  if (size === 0) return new Response('', { status: 200, headers })

  const header = request.headers.get('range')
  if (!header) return new Response(body(0, size - 1), { status: 200, headers: { ...headers, 'Content-Length': String(size) } })

  const range = parseRange(header, size)
  if (!range) return new Response(null, { status: 416, headers: { ...headers, 'Content-Range': `bytes */${size}` } })
  return new Response(body(range.start, range.end), {
    status: 206,
    headers: { ...headers, 'Content-Length': String(range.end - range.start + 1), 'Content-Range': `bytes ${range.start}-${range.end}/${size}` }
  })
}
