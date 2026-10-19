import { duration, itemEnd, type ClipItem, type Timeline } from '@timeline'

/** One clip of the main video track, in seconds. */
export interface Segment {
  clip: ClipItem
  start: number
  end: number
  /** Where in the asset the clip starts. */
  sourceStart: number
}

/** The main video track's clips in order. Overlays, text and audio tracks play in later phases. */
export function segments(t: Timeline): Segment[] {
  const track = t.tracks.find((tr) => tr.kind === 'video')
  if (!track) return []
  return track.items
    .filter((i): i is ClipItem => i.type === 'clip')
    .sort((a, b) => a.at - b.at)
    .map((clip) => ({ clip, start: clip.at / t.fps, end: itemEnd(clip) / t.fps, sourceStart: clip.src_in / t.fps }))
}

export function segmentAt(list: readonly Segment[], time: number): Segment | null {
  return list.find((s) => s.start <= time && time < s.end) ?? null
}

/** The asset time that shows at timeline `time` inside `segment`. */
export function sourceTime(segment: Segment, time: number): number {
  return segment.sourceStart + (time - segment.start) * segment.clip.speed
}

export const timelineSeconds = (t: Timeline) => duration(t) / t.fps
