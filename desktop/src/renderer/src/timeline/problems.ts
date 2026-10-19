import { itemEnd, type ClipItem, type Timeline, type TimelineOp } from '@timeline'
import type { ProjectPreview } from '../../../shared/api'
import { BURNED_IN_TEXT_SHARE, type MediaItem } from '../../../shared/media'
import { mainVideoTrack } from './edits'

export interface Problem {
  id: string
  /** warning: the export will look wrong · info: the export differs from the timeline */
  severity: 'warning' | 'info'
  title: string
  /** Where it is, in seconds. */
  at?: number
  item?: string
  /** A safe one-click fix, as a command. */
  fix?: { label: string; command: string; args?: unknown }
}

const GAP = 0.04
const FLASH_FRAME = 0.3
// Captions sit at ~76% of the height and lower-third titles at 70%: they collide.
const CAPTION_CLASH: ProjectPreview['texts'][number]['kind'] = 'line'

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

/** The ops that close a gap on the main track: everything after it moves left, first item first. */
export function closeGapOps(t: Timeline, at: number): TimelineOp[] {
  const main = mainVideoTrack(t)
  if (!main) return []
  const after = [...main.items].filter((i) => i.at >= at).sort((a, b) => a.at - b.at)
  const before = Math.max(0, ...main.items.filter((i) => i.at < at).map(itemEnd))
  const shift = (after[0]?.at ?? before) - before
  return shift > 0 ? after.map((i) => ({ op: 'move_item', item: i.id, at: i.at - shift })) : []
}

/**
 * What will look wrong in the export, or differ from the timeline, found the way an editor
 * would check: by what the server render draws (brain/render_adapter.py).
 */
export function findProblems(t: Timeline, preview: ProjectPreview | null, media: MediaItem[], canPlay: (assetId: string) => boolean): Problem[] {
  const problems: Problem[] = []
  const fps = t.fps
  const main = mainVideoTrack(t)
  const mainClips = (main?.items ?? []).filter((i): i is ClipItem => i.type === 'clip').sort((a, b) => a.at - b.at)
  const everything = t.tracks.flatMap((tr) => tr.items.map((item) => ({ track: tr, item })))

  if (!mainClips.length && everything.length) {
    problems.push({ id: 'no-main', severity: 'warning', title: 'There is nothing on the main video track, so there is nothing to export.' })
  }

  // Footage the editor can't find anywhere.
  for (const clip of everything.map((e) => e.item).filter((i): i is ClipItem => i.type === 'clip')) {
    if (!canPlay(clip.asset)) problems.push({ id: `missing-${clip.id}`, severity: 'warning', title: `The footage for the clip at ${clock(clip.at / fps)} isn't on this Mac or in the project.`, at: clip.at / fps, item: clip.id })
  }

  // Gaps and flash frames on the main track.
  let cursor = 0
  for (const clip of mainClips) {
    const gap = (clip.at - cursor) / fps
    if (gap > GAP) {
      problems.push({ id: `gap-${clip.id}`, severity: 'warning', title: `A ${gap.toFixed(1)} s gap at ${clock(cursor / fps)} shows as a blank card in the export.`, at: cursor / fps, fix: { label: 'Close the gap', command: 'timeline.closeGap', args: { at: clip.at } } })
    }
    const length = (itemEnd(clip) - clip.at) / fps
    if (length < FLASH_FRAME) {
      problems.push({ id: `flash-${clip.id}`, severity: 'warning', title: `A ${length.toFixed(2)} s clip at ${clock(clip.at / fps)} will flash by.`, at: clip.at / fps, item: clip.id, fix: { label: 'Delete it', command: 'timeline.delete', args: { items: [clip.id] } } })
    }
    if (clip.keyframes.opacity?.length || clip.transition_in) {
      problems.push({ id: `fade-${clip.id}`, severity: 'info', title: `The fade at ${clock(clip.at / fps)} on the main track isn't in exports yet.`, at: clip.at / fps, item: clip.id })
    }
    cursor = itemEnd(clip)
  }

  const music = everything.filter(({ track, item }) => track.kind === 'audio' && !track.muted && item.type === 'clip' && t.assets[item.asset]?.kind === 'audio')
  if (music.length > 1) problems.push({ id: 'music-many', severity: 'info', title: `The export plays one music clip; ${music.length - 1} more won't be heard.`, at: music[1].item.at / fps, item: music[1].item.id })

  // Captions over words already in the picture, and titles where captions sit.
  if (t.captions?.enabled) {
    const used = new Set(mainClips.map((c) => c.asset))
    const burned = media.find((m) => used.has(m.id) && (m.onScreenText?.share ?? 0) >= BURNED_IN_TEXT_SHARE)
    if (burned) {
      const example = burned.onScreenText?.examples[0]
      problems.push({ id: 'burned-in', severity: 'warning', title: `${burned.name} already has words on screen${example ? ` (“${example}”)` : ''}; captions will cover them.`, fix: { label: 'Turn captions off', command: 'captions.toggle' } })
    }
    const words = preview?.words ?? []
    for (const title of preview?.texts.filter((x) => x.kind === CAPTION_CLASH) ?? []) {
      if (!words.some((w) => w.end > title.at && w.start < title.at + title.dur)) continue
      const item = everything.find(({ item: i }) => i.type === 'text' && i.text === title.text && Math.abs(i.at / fps - title.at) < 0.05)?.item
      problems.push({ id: `clash-${item?.id ?? title.at}`, severity: 'warning', title: `The title “${title.text}” at ${clock(title.at)} sits where the captions are.`, at: title.at, item: item?.id, fix: item ? { label: 'Move it to the middle', command: 'text.place', args: { item: item.id, place: 'middle' } } : undefined })
    }
  }
  return problems.sort((a, b) => (a.severity === b.severity ? (a.at ?? -1) - (b.at ?? -1) : a.severity === 'warning' ? -1 : 1))
}
