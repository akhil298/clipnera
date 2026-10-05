'use client';

import { useCallback, useEffect, useState } from 'react';

/**
 * State remembered in this browser (`localStorage`), for per-viewer
 * conveniences only: panel sizes, a collapsed sidebar, a chosen view. Renders
 * `defaultValue` on the server and first client render, then reads the stored
 * value, so hydration never mismatches. Storage can be blocked or full; every
 * access is guarded and the state still works in memory.
 */
export function usePersistentState<T>(key: string | undefined, defaultValue: T): [T, (next: T) => void] {
  const [value, setValue] = useState<T>(defaultValue);

  useEffect(() => {
    if (!key) return;
    try {
      const stored = window.localStorage.getItem(key);
      if (stored !== null) setValue(JSON.parse(stored) as T);
    } catch {
      // Blocked or corrupt storage: keep the default.
    }
  }, [key]);

  const update = useCallback(
    (next: T) => {
      setValue(next);
      if (!key) return;
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // Not remembered this time; the in-memory value still applies.
      }
    },
    [key],
  );

  return [value, update];
}
