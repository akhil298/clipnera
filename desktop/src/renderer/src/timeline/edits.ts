import { findItem, itemEnd, itemFrames, toFrames, type Asset, type ClipItem, type Item, type Timeline, type TimelineOp, type Track, type TrackKind } from '@timeline'

/** Short ids that fit Timeline v1's rules (letters, digits, - and _, at most 40). */
export function newId(prefix: string): string {
  return `${prefix}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
}

export const mainVideoTrack = (t: Timeline): Track | undefined => t.tracks.find((track) => track.kind === 'video')

const trackEnd = (track: Track) => Math.max(0, ...track.items.map(itemEnd))

/** Puts a whole asset at the end of the main video track, or of an audio track for audio. */
export function appendClip(t: Timeline, asset: Asset): TimelineOp[] {
  const kind: TrackKind = asset.kind === 'audio' ? 'audio' : 'video'
  const ops: TimelineOp[] = []
  let track = t.tracks.find((tr) => tr.kind === kind)
  if (!track) {
    const id = kind === 'audio' ? 'a1' : 'v1'
    ops.push({ op: 'add_track', id: t.tracks.some((tr) => tr.id === id) ? newId(kind[0]) : id, kind })
    track = { id: (ops[0] as { id: string }).id, kind, items: [], muted: false, hidden: false, extra: {} }
  }
  const item: ClipItem = {
    type: 'clip',
    id: newId('c'),
    at: trackEnd(track),
    extra: {},
    asset: asset.id,
    src_in: 0,
    src_out: asset.frames,
    speed: 1,
    volume: 1,
    transform: { x: 0.5, y: 0.5, scale: 1, rotation: 0 },
    keyframes: {},
    transition_in: null
  }
  return [...ops, { op: 'add_item', track: track.id, item }]
}

/** Clip items under `frame` (strictly inside, so a cut can land there). */
export function clipsAt(t: Timeline, frame: number, ids?: readonly string[]): ClipItem[] {
  return t.tracks
    .flatMap((track) => track.items)
    .filter((i): i is ClipItem => i.type === 'clip' && i.at < frame && frame < itemEnd(i) && (!ids || ids.includes(i.id)))
}

/** Splits the given clips at `frame`; with none given, the main track's clip under the playhead. */
export function splitAt(t: Timeline, frame: number, ids: readonly string[]): TimelineOp[] {
  let targets = ids.length ? clipsAt(t, frame, ids) : []
  if (!targets.length) {
    const main = mainVideoTrack(t)
    targets = clipsAt(t, frame).filter((c) => main?.items.includes(c))
  }
  return targets.map((clip) => ({ op: 'split_item', item: clip.id, at: frame, new_id: newId('c') }))
}

/** Removes items. Ripple closes the gap on the item's own track. */
export function removeItems(t: Timeline, ids: readonly string[], ripple: boolean): TimelineOp[] {
  // Latest first, so each ripple only moves items that haven't been removed.
  return ids
    .map((id) => findItem(t, id)[1])
    .sort((a, b) => b.at - a.at)
    .map((item) => ({ op: 'remove_item', item: item.id, ripple }))
}

/** Moves the start of a clip: trims its source and shifts it so the far end stays put. */
export function trimStart(t: Timeline, id: string, srcIn: number): TimelineOp[] {
  const clip = asClip(t, id)
  const nextIn = Math.min(Math.max(0, srcIn), clip.src_out - 1)
  const at = clip.at + toFrames((nextIn - clip.src_in) / clip.speed)
  if (at < 0) return []
  const trim: TimelineOp = { op: 'trim_item', item: id, src_in: nextIn }
  const move: TimelineOp = { op: 'move_item', item: id, at }
  // Growing to the left: move first so the longer clip never overlaps its neighbour mid-batch.
  return nextIn < clip.src_in ? [move, trim] : [trim, move]
}

/** Moves the end of a clip within its footage. */
export function trimEnd(t: Timeline, id: string, srcOut: number): TimelineOp[] {
  const clip = asClip(t, id)
  const max = t.assets[clip.asset]?.kind === 'image' ? Number.MAX_SAFE_INTEGER : (t.assets[clip.asset]?.frames ?? clip.src_out)
  return [{ op: 'trim_item', item: id, src_out: Math.max(clip.src_in + 1, Math.min(srcOut, max)) }]
}

/** Changes a clip's speed and shifts what follows on its track, so nothing overlaps or leaves a gap. */
export function setSpeed(t: Timeline, id: string, speed: number): TimelineOp[] {
  const [track, item] = findItem(t, id)
  const clip = asClip(t, id)
  const oldEnd = itemEnd(clip)
  const newEnd = clip.at + toFrames((clip.src_out - clip.src_in) / speed)
  const shift = newEnd - oldEnd
  const later = track.items.filter((i) => i !== item && i.at >= oldEnd)
  const update: TimelineOp = { op: 'update_item', item: id, patch: { speed } }
  // Last item first when pushing right, first item first when pulling left.
  const moves = [...later]
    .sort((a, b) => (shift > 0 ? b.at - a.at : a.at - b.at))
    .map((i): TimelineOp => ({ op: 'move_item', item: i.id, at: i.at + shift }))
  return shift > 0 ? [...moves, update] : [update, ...moves]
}

export function setVolume(t: Timeline, id: string, volume: number): TimelineOp[] {
  asClip(t, id)
  return [{ op: 'update_item', item: id, patch: { volume: Math.min(2, Math.max(0, volume)) } }]
}

/** Moves an item to a new start (frames), on its own track or another. */
export function moveItem(t: Timeline, id: string, at: number, track?: string): TimelineOp[] {
  const [current] = findItem(t, id)
  return [{ op: 'move_item', item: id, at: Math.max(0, Math.round(at)), track: track && track !== current.id ? track : undefined }]
}

export function asClip(t: Timeline, id: string): ClipItem {
  const item: Item = findItem(t, id)[1]
  if (item.type !== 'clip') throw new Error('Only clips can be trimmed or retimed')
  return item
}

export { itemFrames }
