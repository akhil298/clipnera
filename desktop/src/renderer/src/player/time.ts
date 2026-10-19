/** Frame and timecode maths for the viewer. Times are seconds; frames count from 0. */

const DEFAULT_FPS = 30
// Times like 0.1 * 3 come out a hair short of the frame they mean.
const EPSILON = 1e-6

export const rateOf = (fps: number | undefined) => (fps && fps > 0 ? fps : DEFAULT_FPS)

export function timeToFrame(seconds: number, fps: number): number {
  return Math.floor(Math.max(0, seconds) * fps + EPSILON)
}

/** The middle of a frame, so seeking there always shows that frame and not its neighbour. */
export function frameToTime(frame: number, fps: number): number {
  return (Math.max(0, frame) + 0.5) / fps
}

/** HH:MM:SS:FF, counting whole frames at the clip's rate (rounded for 29.97 and 23.976). */
export function formatTimecode(seconds: number, fps: number): string {
  const rate = Math.max(1, Math.round(fps))
  const total = Math.floor(Math.max(0, seconds) * rate + EPSILON)
  const two = (n: number) => String(n).padStart(2, '0')
  const s = Math.floor(total / rate)
  return `${two(Math.floor(s / 3600))}:${two(Math.floor(s / 60) % 60)}:${two(s % 60)}:${two(total % rate)}`
}

export const SHUTTLE_SPEEDS = [1, 2, 4] as const

/**
 * J/L shuttle: the first press plays at 1× in that direction, each further press speeds up
 * to 2× and 4×. Pressing the other way starts again at 1×. Negative is reverse.
 */
export function nextShuttle(current: number, direction: 1 | -1): number {
  if (Math.sign(current) !== direction) return direction
  const index = SHUTTLE_SPEEDS.indexOf(Math.abs(current) as (typeof SHUTTLE_SPEEDS)[number])
  return direction * SHUTTLE_SPEEDS[Math.min(index + 1, SHUTTLE_SPEEDS.length - 1)]
}
