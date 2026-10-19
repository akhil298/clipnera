import { findItem, toFrames } from '@timeline'
import type { Player } from '../player/player'
import { edit, project, sync } from '../state/project'
import { chat } from '../state/chat'
import { MAX_ZOOM, MIN_RANGE_SECONDS, MIN_ZOOM, timelineView } from '../state/selection'
import { appendClip, moveItem, removeItems, setSpeed, setVolume, splitAt, trimEnd, trimStart } from '../timeline/edits'
import { closeGapOps } from '../timeline/problems'
import type { CommandRegistry } from './registry'

function timeline() {
  const t = project.get().timeline
  if (!t) throw new Error('No project is open')
  return t
}

const selection = () => timelineView.get().selection

function requireSelection(): string[] {
  const ids = selection()
  if (!ids.length) throw new Error('Select something on the timeline first')
  return ids
}

function num(value: unknown, name: string): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  throw new Error(`${name} must be a number`)
}

function str(value: unknown, name: string): string {
  if (typeof value === 'string' && value) return value
  throw new Error(`${name} is required`)
}

/** Timeline editing. Every edit is one backend change, so ⌘Z (or the AI's undo) takes it back. */
export function registerTimelineCommands(registry: CommandRegistry, player: Player): () => void {
  const base = { category: 'Edit', aiCanRun: true }
  const playheadFrame = () => toFrames(player.state.get().time * timeline().fps)
  const zoomBy = (factor: number) => timelineView.set(({ zoom }) => ({ zoom: Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom * factor)) }))

  const disposers = [
    registry.register<{ mediaId: string }>({
      ...base,
      id: 'timeline.append',
      needsArgs: true,
      title: 'Add to Timeline',
      description: 'Put a whole media file at the end of the timeline (video on the main track, audio on an audio track).',
      run: async (args) => {
        const asset = timeline().assets[str(args?.mediaId, 'mediaId')]
        if (!asset) throw new Error("That file isn't in the project yet. Wait until it has finished uploading.")
        await edit(appendClip(timeline(), asset))
      }
    }),
    registry.register<{ items?: string[] }>({
      ...base,
      id: 'timeline.split',
      title: 'Split at Playhead',
      description: 'Cut the selected clips (or the main clip under the playhead) in two at the playhead.',
      shortcut: 'Mod+B',
      run: async (args) => {
        const ops = splitAt(timeline(), playheadFrame(), args?.items ?? selection())
        if (!ops.length) throw new Error('There is no clip under the playhead to split')
        await edit(ops)
      }
    }),
    registry.register<{ items?: string[] }>({
      ...base,
      id: 'timeline.delete',
      title: 'Delete',
      description: 'Remove the selected items and close the gap they leave.',
      shortcut: 'Backspace',
      run: async (args) => {
        const ids = args?.items ?? requireSelection()
        await edit(removeItems(timeline(), ids, true))
        timelineView.set({ selection: [] })
      }
    }),
    registry.register<{ items?: string[] }>({
      ...base,
      id: 'timeline.lift',
      title: 'Delete and Leave Gap',
      description: 'Remove the selected items and leave the gap where they were.',
      shortcut: 'Shift+Backspace',
      run: async (args) => {
        await edit(removeItems(timeline(), args?.items ?? requireSelection(), false))
        timelineView.set({ selection: [] })
      }
    }),
    registry.register<{ at: number }>({
      ...base,
      id: 'timeline.closeGap',
      needsArgs: true,
      title: 'Close Gap',
      description: 'Close the gap on the main track before the clip starting at this frame.',
      run: async (args) => {
        const ops = closeGapOps(timeline(), num(args?.at, 'at'))
        if (!ops.length) throw new Error('There is no gap there')
        await edit(ops)
      }
    }),
    registry.register<{ item: string; at: number; track?: string }>({
      ...base,
      id: 'timeline.move',
      needsArgs: true,
      title: 'Move Item',
      description: 'Move an item to start at a frame, optionally on another track.',
      run: (args) => edit(moveItem(timeline(), str(args?.item, 'item'), num(args?.at, 'at'), args?.track))
    }),
    registry.register<{ item: string; srcIn?: number; srcOut?: number }>({
      ...base,
      id: 'timeline.trim',
      needsArgs: true,
      title: 'Trim Clip',
      description: 'Change where a clip starts (srcIn) or ends (srcOut) in its footage, in frames.',
      run: async (args) => {
        const id = str(args?.item, 'item')
        if (args?.srcIn !== undefined) await edit(trimStart(timeline(), id, num(args.srcIn, 'srcIn')))
        if (args?.srcOut !== undefined) await edit(trimEnd(timeline(), id, num(args.srcOut, 'srcOut')))
      }
    }),
    registry.register<{ item?: string; speed: number }>({
      ...base,
      id: 'timeline.setSpeed',
      needsArgs: true,
      title: 'Change Speed',
      description: 'Play a clip faster or slower (0.25–4×). What follows moves along with it.',
      run: (args) => edit(setSpeed(timeline(), args?.item ?? requireSelection()[0], num(args?.speed, 'speed')))
    }),
    registry.register<{ item?: string; volume: number }>({
      ...base,
      id: 'timeline.setVolume',
      needsArgs: true,
      title: 'Change Volume',
      description: "Set a clip's volume (0 silent, 1 as recorded, up to 2).",
      run: (args) => edit(setVolume(timeline(), args?.item ?? requireSelection()[0], num(args?.volume, 'volume')))
    }),
    registry.register<{ items: string[] }>({
      ...base,
      id: 'timeline.select',
      needsArgs: true,
      title: 'Select',
      description: 'Select timeline items by id (an empty list clears the selection).',
      run: (args) => {
        const ids = Array.isArray(args?.items) ? args.items.filter((id): id is string => typeof id === 'string') : []
        ids.forEach((id) => findItem(timeline(), id))
        timelineView.set({ selection: ids })
      }
    }),
    registry.register<{ from: number; to: number }>({
      ...base,
      id: 'timeline.setRange',
      needsArgs: true,
      title: 'Select Range',
      description: 'Select a stretch of the timeline (seconds), for the next request to be about.',
      run: (args) => {
        const from = Math.max(0, Math.min(num(args?.from, 'from'), num(args?.to, 'to')))
        const to = Math.max(num(args?.from, 'from'), num(args?.to, 'to'))
        if (to - from < MIN_RANGE_SECONDS) throw new Error('Select a longer range')
        timelineView.set({ range: { start: from, end: to } })
      }
    }),
    registry.register({
      ...base,
      id: 'timeline.clearRange',
      title: 'Clear Range',
      description: 'Clear the selected range.',
      shortcut: 'Escape',
      // Esc stops the AI first when it is working.
      when: () => timelineView.get().range !== null && !chat.get().running,
      run: () => timelineView.set({ range: null })
    }),
    registry.register({ ...base, id: 'edit.undo', title: 'Undo', description: 'Undo the last change.', shortcut: 'Mod+Z', run: () => sync(() => window.clipnera.project.undo()) }),
    registry.register({ ...base, id: 'edit.redo', title: 'Redo', description: 'Redo the last undone change.', shortcut: 'Shift+Mod+Z', run: () => sync(() => window.clipnera.project.redo()) }),
    registry.register({ ...base, category: 'View', id: 'timeline.zoomIn', title: 'Zoom In', description: 'Zoom the timeline in.', shortcut: 'Mod+=', run: () => zoomBy(1.5) }),
    registry.register({ ...base, category: 'View', id: 'timeline.zoomOut', title: 'Zoom Out', description: 'Zoom the timeline out.', shortcut: 'Mod+-', run: () => zoomBy(1 / 1.5) }),
    registry.register({
      ...base,
      category: 'Playback',
      id: 'player.showTimeline',
      title: 'Show Timeline in Viewer',
      description: 'Make the viewer play the edit instead of a single media file.',
      shortcut: 'Escape',
      run: () => player.showTimeline()
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
