import { findItem, toFrames, type TextItem, type Timeline, type TimelineOp } from '@timeline'
import type { Player } from '../player/player'
import { edit, project } from '../state/project'
import { mainVideoTrack, newId } from '../timeline/edits'
import type { CommandRegistry } from './registry'

/** Where a title sits: the renderer draws these three (brain/render_adapter.py). */
export const TITLE_PLACES = { top: 0.3, middle: 0.4, lower: 0.72 } as const
export type TitlePlace = keyof typeof TITLE_PLACES
const TITLE_SECONDS = 2.5
const TEXT_TRACK = 't1'

function timeline(): Timeline {
  const t = project.get().timeline
  if (!t) throw new Error('No project is open')
  return t
}

function text(value: unknown, name = 'text'): string {
  const s = typeof value === 'string' ? value.trim() : ''
  if (!s || s.length > 200) throw new Error(`${name} must be 1–200 characters`)
  return s
}

/** set_captions needs the track whose speech they show the first time. */
function captionsOps(t: Timeline, change: { enabled?: boolean; style?: string }): TimelineOp[] {
  const follow = t.captions ? undefined : mainVideoTrack(t)?.id
  if (!t.captions && !follow) throw new Error('Put a clip on the timeline first')
  return [{ op: 'set_captions', ...change, ...(follow ? { follow } : {}) }]
}

export function addTitleOps(t: Timeline, words: string, frame: number, place: TitlePlace = 'lower'): TimelineOp[] {
  const ops: TimelineOp[] = []
  let track = t.tracks.find((tr) => tr.kind === 'text')
  if (!track) {
    ops.push({ op: 'add_track', id: t.tracks.some((tr) => tr.id === TEXT_TRACK) ? newId('t') : TEXT_TRACK, kind: 'text' })
    track = { id: (ops[0] as { id: string }).id, kind: 'text', items: [], muted: false, hidden: false, extra: {} }
  }
  const dur = toFrames(TITLE_SECONDS * t.fps)
  // Titles on one track can't overlap: start after any title already under the playhead.
  const at = Math.max(frame, ...track.items.filter((i) => i.at <= frame && frame < i.at + (i.type === 'text' ? i.dur : 0)).map((i) => i.at + (i.type === 'text' ? i.dur : 0)))
  const item: TextItem = { type: 'text', id: newId('x'), at, extra: {}, text: words, style: 'studio', dur, transform: { x: 0.5, y: TITLE_PLACES[place], scale: 1, rotation: 0 } }
  return [...ops, { op: 'add_item', track: track.id, item }]
}

export function registerCaptionCommands(registry: CommandRegistry, player: Player): () => void {
  const base = { category: 'Text', aiCanRun: true }
  const playheadFrame = () => toFrames(player.state.get().time * timeline().fps)
  const disposers = [
    registry.register({
      ...base,
      id: 'captions.toggle',
      title: 'Captions On / Off',
      description: 'Show or hide captions of what is said.',
      run: () => edit(captionsOps(timeline(), { enabled: !(timeline().captions?.enabled ?? false) }))
    }),
    registry.register<{ style: string }>({
      ...base,
      id: 'captions.setStyle',
      needsArgs: true,
      title: 'Caption Style',
      description: 'Pick the caption style by id (karaoke, simple, punch, …); turns captions on.',
      run: (args) => edit(captionsOps(timeline(), { enabled: true, style: text(args?.style, 'style') }))
    }),
    registry.register<{ text: string; place?: TitlePlace }>({
      ...base,
      id: 'text.add',
      needsArgs: true,
      title: 'Add Title',
      description: 'Put a title on screen at the playhead for 2.5 s: at the top, in the middle or as a lower third.',
      run: (args) => edit(addTitleOps(timeline(), text(args?.text), playheadFrame(), args?.place ?? 'lower'))
    }),
    registry.register<{ item: string; text: string }>({
      ...base,
      id: 'text.edit',
      needsArgs: true,
      title: 'Edit Title',
      description: "Change a title's words.",
      run: (args) => edit([{ op: 'update_item', item: text(args?.item, 'item'), patch: { text: text(args?.text) } }])
    }),
    registry.register<{ item: string; place: TitlePlace }>({
      ...base,
      id: 'text.place',
      needsArgs: true,
      title: 'Move Title',
      description: 'Put a title at the top, in the middle or as a lower third.',
      run: (args) => {
        const place = args?.place
        if (!place || !(place in TITLE_PLACES)) throw new Error('place must be top, middle or lower')
        const item = findItem(timeline(), text(args?.item, 'item'))[1]
        if (item.type !== 'text') throw new Error('That is not a title')
        return edit([{ op: 'update_item', item: item.id, patch: { transform: { y: TITLE_PLACES[place] } } }])
      }
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
