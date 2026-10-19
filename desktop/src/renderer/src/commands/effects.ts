import { itemEnd, toFrames, type ClipItem, type KeyframeProp, type Timeline, type TimelineOp } from '@timeline'
import type { Player } from '../player/player'
import { edit, project } from '../state/project'
import { chat } from '../state/chat'
import { timelineView } from '../state/selection'
import { asClip, mainVideoTrack } from '../timeline/edits'
import type { CommandRegistry } from './registry'

/** The zooms the panel offers; 1.14× is the AI's own punch-in. */
export const ZOOMS = { none: 1, punch: 1.14, tight: 1.3 } as const

function timeline(): Timeline {
  const t = project.get().timeline
  if (!t) throw new Error('No project is open')
  return t
}

/** The clip an effect applies to: the one named, else the selected clip, else the main clip under the playhead. */
export function targetClip(t: Timeline, frame: number, id?: string): ClipItem | null {
  if (id) return asClip(t, id)
  const selected = timelineView.get().selection
  const picked = t.tracks.flatMap((tr) => tr.items).find((i): i is ClipItem => i.type === 'clip' && selected.includes(i.id))
  if (picked) return picked
  return mainVideoTrack(t)?.items.find((i): i is ClipItem => i.type === 'clip' && i.at <= frame && frame < itemEnd(i)) ?? null
}

/** Keyframes without one property: a steady value replaces a moving one. */
const without = (clip: ClipItem, prop: KeyframeProp) => Object.fromEntries(Object.entries(clip.keyframes).filter(([key]) => key !== prop))

export function zoomOps(clip: ClipItem, scale: number): TimelineOp[] {
  if (!(scale >= 1 && scale <= 3)) throw new Error('Zoom must be between 1× and 3×')
  return [{ op: 'update_item', item: clip.id, patch: { transform: { scale }, keyframes: without(clip, 'scale') } }]
}

export function frameOps(clip: ClipItem, x: number): TimelineOp[] {
  if (!(x >= 0 && x <= 1)) throw new Error('Framing must be between 0 (left) and 1 (right)')
  return [{ op: 'update_item', item: clip.id, patch: { transform: { x }, keyframes: without(clip, 'x') } }]
}

export function registerEffectCommands(registry: CommandRegistry, player: Player): () => void {
  const base = { category: 'Effects', aiCanRun: true, needsArgs: true }
  const clip = (id?: string) => {
    const t = timeline()
    const found = targetClip(t, toFrames(player.state.get().time * t.fps), id)
    if (!found) throw new Error('Select a clip, or put the playhead over one')
    return found
  }
  const disposers = [
    registry.register<{ item?: string; scale: number }>({
      ...base,
      id: 'effects.zoom',
      title: 'Zoom',
      description: 'Hold a clip zoomed in (1 = none, 1.14 = punch-in, 1.3 = tight); replaces a moving zoom.',
      run: (args) => edit(zoomOps(clip(args?.item), Number(args?.scale)))
    }),
    registry.register<{ x: number; y: number; sourceX: number }>({
      ...base,
      category: 'View',
      aiCanRun: false,
      id: 'point.set',
      title: 'Point at a Spot',
      description: 'Point at a spot in the picture, for the next request to be about.',
      run: (args) => {
        const { x, y, sourceX } = args ?? ({} as { x: number; y: number; sourceX: number })
        if (![x, y, sourceX].every((v) => typeof v === 'number' && v >= 0 && v <= 1)) throw new Error('A spot is given as shares of the frame, 0–1')
        timelineView.set({ point: { x, y, sourceX } })
      }
    }),
    registry.register({
      ...base,
      category: 'View',
      aiCanRun: false,
      needsArgs: false,
      id: 'point.clear',
      title: 'Clear the Spot',
      description: 'Stop pointing at a spot in the picture.',
      shortcut: 'Escape',
      when: () => timelineView.get().point !== null && !chat.get().running,
      run: () => timelineView.set({ point: null })
    }),
    registry.register({
      ...base,
      needsArgs: false,
      id: 'effects.zoomHere',
      title: 'Zoom In on the Spot',
      description: 'Frame the clip under the playhead on the spot pointed at, zoomed in (1.3×).',
      run: async () => {
        const point = timelineView.get().point
        if (!point) throw new Error('Point at a spot in the picture first')
        const target = clip()
        await edit([...frameOps(target, point.sourceX), ...zoomOps({ ...target, keyframes: Object.fromEntries(Object.entries(target.keyframes).filter(([k]) => k !== 'x')) }, ZOOMS.tight)])
        timelineView.set({ point: null })
      }
    }),
    registry.register<{ look: string }>({
      ...base,
      category: 'Colour',
      id: 'look.set',
      title: 'Colour Look',
      description: 'Give the whole edit a colour look: natural, clean_bright, warm_film, teal_orange, moody, vivid, bw_punch.',
      run: (args) => {
        const look = String(args?.look ?? '')
        const offered = project.get().looks
        if (offered.length && !offered.some((l) => l.id === look)) throw new Error(`Unknown look ${look}`)
        return edit([{ op: 'set_project', look }])
      }
    }),
    registry.register<{ item?: string; x: number }>({
      ...base,
      id: 'effects.frame',
      title: 'Framing',
      description: "Move a clip's crop left or right (0 left, 0.5 centre, 1 right).",
      run: (args) => edit(frameOps(clip(args?.item), Number(args?.x)))
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
