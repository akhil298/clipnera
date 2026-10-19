import { duration, itemEnd, toFrames, type ClipItem, type SfxItem, type Timeline, type TimelineOp } from '@timeline'
import type { Player } from '../player/player'
import { edit, project } from '../state/project'
import { newId } from '../timeline/edits'
import type { CommandRegistry } from './registry'

const SFX_TRACK = 'sfx'
const MUSIC_TRACK = 'music'
// −14 dB, the level the AI gives music under speech.
export const MUSIC_VOLUME = 0.2

function timeline(): Timeline {
  const t = project.get().timeline
  if (!t) throw new Error('No project is open')
  return t
}

/** An audio track with this id, added first when there isn't one. */
function audioTrack(t: Timeline, id: string): { ops: TimelineOp[]; items: Timeline['tracks'][number]['items'] } {
  const track = t.tracks.find((tr) => tr.id === id)
  if (track) return { ops: [], items: track.items }
  return { ops: [{ op: 'add_track', id, kind: 'audio' }], items: [] }
}

/** The library keeps sounds under the API host; the timeline stores the path, like the AI's sounds. */
const pathOf = (url: string) => (/^https?:/.test(url) ? new URL(url).pathname : url)

export function addSoundOps(t: Timeline, sound: { id: string; url: string; seconds: number }, frame: number): TimelineOp[] {
  const { ops, items } = audioTrack(t, SFX_TRACK)
  const dur = Math.max(1, toFrames(sound.seconds * t.fps))
  // Sounds on one track can't overlap: after any sound already playing there.
  const at = Math.max(frame, ...items.filter((i) => i.at <= frame && frame < itemEnd(i)).map(itemEnd))
  const item: SfxItem = { type: 'sfx', id: newId('s'), at, extra: { url: pathOf(sound.url) }, name: sound.id, dur, gain_db: 0 }
  return [...ops, { op: 'add_item', track: SFX_TRACK, item }]
}

/** An audio file as the edit's music: from the start, cut to the edit's length, at −14 dB. */
export function addMusicOps(t: Timeline, assetId: string): TimelineOp[] {
  const asset = t.assets[assetId]
  if (!asset || asset.kind !== 'audio') throw new Error('Pick an audio file for the music')
  const { ops, items } = audioTrack(t, MUSIC_TRACK)
  const length = duration(t) || asset.frames
  const at = Math.max(0, ...items.map(itemEnd))
  const item: ClipItem = {
    type: 'clip', id: newId('m'), at, extra: {}, asset: assetId, src_in: 0, src_out: Math.min(asset.frames, Math.max(1, length - at)),
    speed: 1, volume: MUSIC_VOLUME, transform: { x: 0.5, y: 0.5, scale: 1, rotation: 0 }, keyframes: {}, transition_in: null
  }
  return [...ops, { op: 'add_item', track: MUSIC_TRACK, item }]
}

export function registerSoundCommands(registry: CommandRegistry, player: Player): () => void {
  const base = { category: 'Sound', aiCanRun: true, needsArgs: true }
  const disposers = [
    registry.register<{ id: string; url: string; seconds: number }>({
      ...base,
      id: 'sounds.add',
      title: 'Add Sound Effect',
      description: 'Put a sound effect from the library at the playhead.',
      run: (args) => {
        if (!args?.id || !args.url) throw new Error('Pick a sound from the library')
        return edit(addSoundOps(timeline(), { id: args.id, url: args.url, seconds: Number(args.seconds) || 1 }, toFrames(player.state.get().time * timeline().fps)))
      }
    }),
    registry.register<{ mediaId: string }>({
      ...base,
      id: 'music.add',
      title: 'Use as Music',
      description: 'Lay an audio file under the edit as its music, at −14 dB; it ducks under speech.',
      run: (args) => edit(addMusicOps(timeline(), String(args?.mediaId ?? '')))
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
