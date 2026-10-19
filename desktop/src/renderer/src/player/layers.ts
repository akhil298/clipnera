import { itemEnd, type Timeline } from '@timeline'
import { mainVideoTrack } from '../timeline/edits'

/**
 * What the export draws over the main picture (backend brain/render_adapter.py _layers →
 * edit_engine/compose.py), for the viewer to draw the same: the overlay tracks' footage and
 * stills, the graphic tracks' flashes and shelf graphics. Later tracks draw on top.
 */
export type Layer =
  | { kind: 'solid'; id: string; colour: string; opacity: number }
  | { kind: 'graphic'; id: string; graphic: string; offset: number; opacity: number }
  | { kind: 'video' | 'image'; id: string; asset: string; sourceTime: number; speed: number; scale: number; x: number; y: number; opacity: number }

const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length

/** The layers on screen at `time` (seconds), bottom first. */
export function layersAt(t: Timeline, time: number): Layer[] {
  const main = mainVideoTrack(t)
  const frame = time * t.fps
  const layers: Layer[] = []
  for (const track of t.tracks) {
    if (track === main || track.hidden || !['video', 'overlay', 'graphic'].includes(track.kind)) continue
    for (const item of track.items) {
      if (frame < item.at || frame >= itemEnd(item)) continue
      const offset = (frame - item.at) / t.fps
      if (item.type === 'graphic') {
        if (typeof item.extra.solid === 'string') layers.push({ kind: 'solid', id: item.id, colour: item.extra.solid, opacity: 1 })
        else if (typeof item.extra.graphic === 'string') layers.push({ kind: 'graphic', id: item.id, graphic: item.extra.graphic, offset, opacity: 1 })
      } else if (item.type === 'clip') {
        const asset = t.assets[item.asset]
        if (!asset || asset.kind === 'audio') continue
        const fade = item.transition_in?.type === 'fade' && item.transition_in.frames > 0 ? Math.min(1, (frame - item.at) / item.transition_in.frames) : 1
        const opacity = item.keyframes.opacity?.length ? mean(item.keyframes.opacity.map((k) => k.v)) : 1
        const scale = item.keyframes.scale?.length ? mean(item.keyframes.scale.map((k) => k.v)) : item.transform.scale
        layers.push({
          kind: asset.kind, id: item.id, asset: item.asset, sourceTime: item.src_in / t.fps + offset * item.speed, speed: item.speed,
          scale, x: item.transform.x, y: item.transform.y, opacity: Math.max(0, Math.min(1, opacity)) * fade
        })
      }
    }
  }
  return layers
}
