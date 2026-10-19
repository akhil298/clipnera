import { duration, itemEnd, type Item, type Timeline } from '@timeline'
import type { MediaAnalysisResponse } from '../../shared/api'
import type { MediaItem } from '../../shared/media'

const s = (frames: number, fps: number) => Math.round((frames / fps) * 100) / 100

function what(item: Item, t: Timeline, names: Map<string, string>): string {
  switch (item.type) {
    case 'clip':
      return names.get(item.asset) ?? t.assets[item.asset]?.key.split('/').pop() ?? item.asset
    case 'text':
      return item.text
    case 'sfx':
      return item.name
    case 'music':
      return item.track
    case 'graphic':
      return 'graphic'
  }
}

/** The project as an outside agent reads it: seconds, not frames, and names, not keys. */
export function summarizeProject(title: string, version: number, t: Timeline, media: MediaItem[]) {
  const names = new Map(media.map((m) => [m.id, m.name]))
  return {
    title,
    version,
    seconds: s(duration(t), t.fps),
    fps: t.fps,
    size: `${t.width}x${t.height}`,
    look: t.look,
    captions: t.captions ? { on: t.captions.enabled, style: t.captions.style } : null,
    tracks: t.tracks.map((track) => ({
      id: track.id,
      kind: track.kind,
      items: [...track.items].sort((a, b) => a.at - b.at).map((item) => ({
        id: item.id,
        type: item.type,
        start: s(item.at, t.fps),
        end: s(itemEnd(item), t.fps),
        what: what(item, t, names),
        ...(item.type === 'clip' ? { speed: item.speed, volume: item.volume, zoom: item.transform.scale } : {})
      }))
    }))
  }
}

/** The footage, and what Clipnera's AI understood of it. */
export function summarizeMedia(media: MediaItem[], analysis: Record<string, MediaAnalysisResponse>) {
  return media.map((m) => {
    const found = analysis[m.id]
    return {
      id: m.id,
      name: m.name,
      kind: m.kind,
      status: m.status,
      seconds: m.info?.durationSeconds ?? null,
      understanding: found?.status ?? null,
      summary: found?.findings?.summary ?? null,
      moments: found?.findings?.moments ?? []
    }
  })
}
