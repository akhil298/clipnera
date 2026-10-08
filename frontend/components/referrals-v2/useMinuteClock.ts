'use client';

import { useEffect, useState } from 'react';

/** Countdowns here show minutes, so the clock ticks twice a minute. */
const TICK_MS = 30_000;

export function useMinuteClock(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}
