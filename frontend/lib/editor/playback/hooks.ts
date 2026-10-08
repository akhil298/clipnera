import { useCallback, useSyncExternalStore } from 'react';

import type { ClockState, PlaybackClock } from './clock';

/**
 * Re-render only when `select(state)` changes. Return a primitive (a frame, an
 * index, a flag); `throttleMs` caps how often time ticks are even looked at.
 */
export function useClockSelector<T>(clock: PlaybackClock, select: (state: ClockState) => T, throttleMs = 0): T {
  const subscribe = useCallback((onChange: () => void) => clock.subscribe(onChange, throttleMs), [clock, throttleMs]);
  const read = () => select(clock.getState());
  return useSyncExternalStore(subscribe, read, read);
}

/** Time in seconds, at most every `throttleMs` (a timecode readout: 100 ms). */
export const useClockTime = (clock: PlaybackClock, throttleMs = 100): number =>
  useClockSelector(clock, (s) => s.time, throttleMs);

/** The current frame; re-renders once per frame at most (preview overlays only). */
export const useClockFrame = (clock: PlaybackClock): number => useClockSelector(clock, (s) => s.frame);

export const useClockPlaying = (clock: PlaybackClock): boolean => useClockSelector(clock, (s) => s.playing);

export const useClockBuffering = (clock: PlaybackClock): boolean => useClockSelector(clock, (s) => s.buffering);
