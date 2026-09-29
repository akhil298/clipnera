'use client';

import { useCallback, useRef, useState } from 'react';

/** Edits with the same key this close together (a slider drag, a caption drag) undo as one step. */
const COALESCE_MS = 800;
const MAX_STEPS = 100;

interface History<T> {
  past: T[];
  present: T;
  future: T[];
}

/**
 * State with undo and redo. `commit` records a step; `replace` changes the
 * present without one, for corrections the user did not make (plan fallbacks,
 * brand kit defaults).
 */
export function useHistory<T>(init: () => T) {
  const [history, setHistory] = useState<History<T>>(() => ({ past: [], present: init(), future: [] }));
  const lastCommit = useRef<{ key?: string; at: number }>({ at: 0 });

  const commit = useCallback((update: (prev: T) => T, coalesceKey?: string) => {
    const now = Date.now();
    const merge =
      coalesceKey !== undefined && lastCommit.current.key === coalesceKey && now - lastCommit.current.at < COALESCE_MS;
    lastCommit.current = { key: coalesceKey, at: now };
    setHistory((h) => {
      const next = update(h.present);
      if (Object.is(next, h.present)) return h;
      return {
        past: merge && h.past.length ? h.past : [...h.past, h.present].slice(-MAX_STEPS),
        present: next,
        future: [],
      };
    });
  }, []);

  const replace = useCallback((update: (prev: T) => T) => {
    setHistory((h) => ({ ...h, present: update(h.present) }));
  }, []);

  const undo = useCallback(() => {
    lastCommit.current = { at: 0 };
    setHistory((h) =>
      h.past.length
        ? { past: h.past.slice(0, -1), present: h.past[h.past.length - 1], future: [h.present, ...h.future] }
        : h,
    );
  }, []);

  const redo = useCallback(() => {
    lastCommit.current = { at: 0 };
    setHistory((h) =>
      h.future.length ? { past: [...h.past, h.present], present: h.future[0], future: h.future.slice(1) } : h,
    );
  }, []);

  return {
    state: history.present,
    commit,
    replace,
    undo,
    redo,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
  };
}
