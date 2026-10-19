import type { Timeline, TimelineOp } from '@timeline'

/** The backend takes at most this many ops per change (editor/schema.py EditorOpsRequest). */
export const OPS_PER_CHANGE = 200

/**
 * The ops that turn `current` into `take`: everything comes off, the take's tracks are made to
 * match, its items go back on, then captions and the project settings. As ordinary ops it is an
 * edit like any other, so Undo takes a restore back.
 */
export function restoreOps(current: Timeline, take: Timeline): TimelineOp[] {
  const ops: TimelineOp[] = []
  for (const track of current.tracks) for (const item of track.items) ops.push({ op: 'remove_item', item: item.id })

  for (const asset of Object.values(take.assets)) if (!current.assets[asset.id]) ops.push({ op: 'add_asset', asset })

  const keep = new Set(take.tracks.map((t) => t.id))
  for (const track of take.tracks) {
    const now = current.tracks.find((t) => t.id === track.id)
    if (!now) ops.push({ op: 'add_track', id: track.id, kind: track.kind })
    else if (now.kind !== track.kind) throw new Error(`Track ${track.id} changed kind since this take`)
    if (!now || now.muted !== track.muted || now.hidden !== track.hidden) ops.push({ op: 'update_track', track: track.id, muted: track.muted, hidden: track.hidden })
  }

  // Captions first, so a track they follow can come off afterwards.
  if (take.captions) {
    const { enabled, style, language, follow } = take.captions
    ops.push({ op: 'set_captions', enabled, style, language, follow })
  } else if (current.captions?.enabled) {
    ops.push({ op: 'set_captions', enabled: false })
  }
  const following = take.captions?.follow ?? current.captions?.follow
  for (const track of current.tracks) if (!keep.has(track.id) && track.id !== following) ops.push({ op: 'remove_track', track: track.id })

  for (const track of take.tracks) for (const item of track.items) ops.push({ op: 'add_item', track: track.id, item })

  const order = [...take.tracks.map((t) => t.id), ...current.tracks.filter((t) => !keep.has(t.id) && t.id === following).map((t) => t.id)]
  ops.push({ op: 'reorder_tracks', order })
  if (current.look !== take.look || current.width !== take.width || current.height !== take.height) {
    ops.push({ op: 'set_project', look: take.look, width: take.width, height: take.height })
  }
  return ops
}

/** Splits ops into changes the backend takes. */
export function batches(ops: TimelineOp[], size = OPS_PER_CHANGE): TimelineOp[][] {
  const out: TimelineOp[][] = []
  for (let i = 0; i < ops.length; i += size) out.push(ops.slice(i, i + size))
  return out
}
