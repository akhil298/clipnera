import { itemEnd, toFrames, type Asset, type ClipItem, type GraphicItem, type Timeline, type TimelineOp } from '@timeline'
import type { Player } from '../player/player'
import { graphics, loadGraphics } from '../state/graphics'
import { edit, project } from '../state/project'
import { newId } from '../timeline/edits'
import type { CommandRegistry } from './registry'
import { addMusicOps } from './sounds'

const GRAPHICS_TRACK = 'graphics'
const OVERLAY_TRACK = 'broll'
// B-roll comes in over a quarter second, as the AI's does.
const BROLL_FADE_FRAMES = 6

function timeline(): Timeline {
  const t = project.get().timeline
  if (!t) throw new Error('No project is open')
  return t
}

/** A track of `kind` with this id, added first when there isn't one; and where on it `frame` is free. */
function trackAt(t: Timeline, id: string, kind: 'graphic' | 'overlay', frame: number): { ops: TimelineOp[]; at: number } {
  const track = t.tracks.find((tr) => tr.id === id)
  if (!track) return { ops: [{ op: 'add_track', id, kind }], at: frame }
  return { ops: [], at: Math.max(frame, ...track.items.filter((i) => i.at <= frame && frame < itemEnd(i)).map(itemEnd)) }
}

/** A shelf graphic at `frame`, for its own length. */
export function addGraphicOps(t: Timeline, graphic: { id: string; seconds: number }, frame: number): TimelineOp[] {
  const { ops, at } = trackAt(t, GRAPHICS_TRACK, 'graphic', frame)
  const item: GraphicItem = { type: 'graphic', id: newId('g'), at, dur: Math.max(1, toFrames(graphic.seconds * t.fps)), extra: { graphic: graphic.id } }
  return [...ops, { op: 'add_item', track: GRAPHICS_TRACK, item }]
}

/** A B-roll shot the backend copied into the project, as an asset and a cutaway over the edit at `frame`. */
export function addBrollOps(t: Timeline, shot: { key: string; seconds: number; width: number; height: number; title: string }, frame: number): TimelineOp[] {
  const assetId = newId('br')
  const frames = Math.max(1, toFrames(shot.seconds * t.fps))
  const { ops, at } = trackAt(t, OVERLAY_TRACK, 'overlay', frame)
  const clip: ClipItem = {
    type: 'clip', id: newId('b'), at, extra: { name: shot.title }, asset: assetId, src_in: 0, src_out: frames, speed: 1, volume: 0,
    transform: { x: 0.5, y: 0.5, scale: 1, rotation: 0 }, keyframes: {}, transition_in: { type: 'fade', frames: BROLL_FADE_FRAMES }
  }
  return [
    { op: 'add_asset', asset: { id: assetId, kind: 'video', key: shot.key, proxy: null, frames, width: shot.width, height: shot.height, has_audio: false } },
    ...ops,
    { op: 'add_item', track: OVERLAY_TRACK, item: clip }
  ]
}

/** A shelf track the backend copied into the project, laid under the edit as its music. */
export function addShelfMusicOps(t: Timeline, track: { key: string; seconds: number; name: string }): TimelineOp[] {
  const asset: Asset = { id: newId('mu'), kind: 'audio', key: track.key, proxy: null, frames: Math.max(1, toFrames(track.seconds * t.fps)), width: null, height: null, has_audio: true }
  // The clip keeps the track's name, for the Music panel and the timeline.
  return [{ op: 'add_asset', asset }, ...addMusicOps({ ...t, assets: { ...t.assets, [asset.id]: asset } }, asset.id).map((op) =>
    op.op === 'add_item' ? { ...op, item: { ...op.item, extra: { ...op.item.extra, name: track.name } } } : op
  )]
}

export function registerLibraryCommands(registry: CommandRegistry, player: Player): () => void {
  const base = { aiCanRun: true, needsArgs: true }
  const playhead = () => toFrames(player.state.get().time * timeline().fps)
  const disposers = [
    registry.register<{ id: string }>({
      ...base,
      category: 'Effects',
      id: 'graphics.add',
      title: 'Add Graphic',
      description: 'Put an animated graphic from the shelf (light leak, glitch, confetti…) over the edit at the playhead.',
      run: async (args) => {
        await loadGraphics()
        const graphic = graphics.get().byId[String(args?.id ?? '')]
        if (!graphic) throw new Error('Pick a graphic from the shelf')
        return edit(addGraphicOps(timeline(), graphic, playhead()))
      }
    }),
    registry.register<{ id: string }>({
      ...base,
      category: 'Sound',
      id: 'music.addTrack',
      title: 'Use Clipnera Music',
      description: 'Lay one of Clipnera’s own music beds under the edit; it ducks under speech and plays on to the end.',
      run: async (args) => {
        if (!args?.id) throw new Error('Pick a track from the music shelf')
        const id = String(args.id)
        const [track, shelf] = await Promise.all([window.clipnera.project.addMusic(id), window.clipnera.project.music('')])
        return edit(addShelfMusicOps(timeline(), { ...track, name: shelf.find((m) => m.id === id)?.name ?? 'Music' }))
      }
    }),
    registry.register<{ id: string; title?: string }>({
      ...base,
      category: 'Media',
      id: 'broll.add',
      title: 'Add B-roll',
      description: 'Put a public-domain B-roll shot over the edit at the playhead; the voice carries on under it.',
      run: async (args) => {
        if (!args?.id) throw new Error('Pick a B-roll shot')
        const shot = await window.clipnera.project.addBroll(String(args.id))
        return edit(addBrollOps(timeline(), { ...shot, title: args.title ?? 'B-roll' }, playhead()))
      }
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
