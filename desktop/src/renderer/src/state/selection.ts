import { createStore } from './store'

/** A selected stretch of the timeline, in seconds (Select & ask). */
export interface TimeRange {
  start: number
  end: number
}

/** A spot pointed at in the picture: where in the frame (0–1), and where across the footage that is. */
export interface PointedSpot {
  x: number
  y: number
  sourceX: number
}

/** Selected timeline items, the selected range, the spot pointed at, and the timeline's zoom (pixels per second). */
export const timelineView = createStore<{ selection: string[]; range: TimeRange | null; point: PointedSpot | null; zoom: number }>({ selection: [], range: null, point: null, zoom: 40 })

export const MIN_ZOOM = 2
export const MAX_ZOOM = 400
// Shorter than this and it's a click, not a range.
export const MIN_RANGE_SECONDS = 0.2

/** "0:42–1:10" */
export function rangeLabel(range: TimeRange): string {
  const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
  return `${clock(range.start)}–${clock(range.end)}`
}
