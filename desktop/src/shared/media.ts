/** Media library types shared by the main process and the renderer. */

/** What clipnera-engine's `probe` returns (engine/Sources/Probe.swift). */
export interface ProbeResult {
  durationSeconds: number
  fileSize: number
  hasVideo: boolean
  hasAudio: boolean
  width?: number
  height?: number
  fps?: number
  videoCodec?: string
  sampleRate?: number
  audioChannels?: number
  audioCodec?: string
}

/**
 * reading: probing the file · preparing: making the small editing copy · uploading: sending
 * that copy to the project so the AI can use it · ready · failed
 */
export type MediaStatus = 'reading' | 'preparing' | 'uploading' | 'ready' | 'failed'

export interface MediaItem {
  id: string
  /** The original file. Clipnera never changes or deletes it. */
  path: string
  name: string
  kind: 'video' | 'audio' | 'unknown'
  status: MediaStatus
  /** 0–1 while preparing or uploading. */
  progress: number
  info?: ProbeResult
  /** clipnera-media:// URL of the thumbnail. */
  thumbnail?: string
  /** Words already burned into the picture (subtitles), from a scan of sampled frames. */
  onScreenText?: { share: number; examples: string[] }
  error?: string
}

export const MEDIA_SCHEME = 'clipnera-media'

/** Files clipnera-media:// may serve from an item's cache folder. */
export const CACHE_FILES = { thumbnail: 'thumb.jpg', proxy: 'proxy.mp4', audioProxy: 'proxy.m4a' } as const

/** clipnera-media://<id>/source plays an audio item's original file; video plays its editing copy. */
export const SOURCE_FILE = 'source'

export function playbackUrl(item: Pick<MediaItem, 'id' | 'kind'>): string {
  return `${MEDIA_SCHEME}://${item.id}/${item.kind === 'audio' ? SOURCE_FILE : CACHE_FILES.proxy}`
}

/** A file whose picture carries words this often (its text scan) has subtitles burned in: no captions over them. */
export const BURNED_IN_TEXT_SHARE = 0.1
