import { describe, expect, it } from 'vitest'
import { formatTimecode, frameToTime, nextShuttle, rateOf, timeToFrame } from './time'

describe('timecode', () => {
  it('formats hours, minutes, seconds and frames', () => {
    expect(formatTimecode(0, 30)).toBe('00:00:00:00')
    expect(formatTimecode(1.5, 30)).toBe('00:00:01:15')
    expect(formatTimecode(3725 + 23 / 24, 24)).toBe('01:02:05:23')
  })

  it('rounds fractional rates and never shows a frame past the rate', () => {
    expect(formatTimecode(0.999, 29.97)).toBe('00:00:00:29')
    expect(formatTimecode(-1, 30)).toBe('00:00:00:00')
  })

  it('lands on the intended frame despite float error', () => {
    expect(timeToFrame(0.1 * 3, 10)).toBe(3)
    for (const frame of [0, 1, 29, 30, 899]) expect(timeToFrame(frameToTime(frame, 30), 30)).toBe(frame)
  })

  it('falls back to 30 fps when the rate is unknown', () => {
    expect(rateOf(undefined)).toBe(30)
    expect(rateOf(0)).toBe(30)
    expect(rateOf(25)).toBe(25)
  })
})

describe('shuttle', () => {
  it('speeds up each press and caps at 4×', () => {
    expect(nextShuttle(0, 1)).toBe(1)
    expect(nextShuttle(1, 1)).toBe(2)
    expect(nextShuttle(2, 1)).toBe(4)
    expect(nextShuttle(4, 1)).toBe(4)
  })

  it('restarts at 1× when the direction changes', () => {
    expect(nextShuttle(4, -1)).toBe(-1)
    expect(nextShuttle(-1, -1)).toBe(-2)
    expect(nextShuttle(-2, 1)).toBe(1)
  })
})
