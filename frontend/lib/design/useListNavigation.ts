'use client';

import { type KeyboardEvent, useEffect, useState } from 'react';

export interface ListNavigation {
  /** The highlighted option, or `null` when the list is empty. */
  activeId: string | null;
  setActiveId: (id: string | null) => void;
  /** Put on the element that keeps focus (usually the combobox input). */
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
}

/**
 * `aria-activedescendant` navigation for a combobox and its listbox: focus
 * stays in the input while ↑↓, Home/End (with ⌘/Ctrl, so text editing keeps
 * them) and Enter act on the highlighted option. Disabled options are left out
 * of `ids` by the caller. The highlight resets to the first option whenever
 * the current one disappears (typing filtered it out).
 */
export function useListNavigation(ids: ReadonlyArray<string>, onChoose: (id: string) => void, loop = true): ListNavigation {
  const [activeId, setActiveId] = useState<string | null>(ids[0] ?? null);
  const key = ids.join('\u0000');

  useEffect(() => {
    if (activeId === null || !ids.includes(activeId)) setActiveId(ids[0] ?? null);
    // `key` stands in for `ids`, which is usually a fresh array each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const move = (to: number) => {
    if (ids.length === 0) return;
    const index = loop ? (to + ids.length) % ids.length : Math.max(0, Math.min(to, ids.length - 1));
    setActiveId(ids[index]);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.nativeEvent.isComposing) return;
    const current = activeId === null ? -1 : ids.indexOf(activeId);
    const jump = event.metaKey || event.ctrlKey;
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        move(current + 1);
        return;
      case 'ArrowUp':
        event.preventDefault();
        move(current < 0 ? ids.length - 1 : current - 1);
        return;
      case 'Home':
        if (!jump) return;
        event.preventDefault();
        move(0);
        return;
      case 'End':
        if (!jump) return;
        event.preventDefault();
        move(ids.length - 1);
        return;
      case 'Enter':
        if (activeId === null) return;
        event.preventDefault();
        onChoose(activeId);
    }
  };

  return { activeId, setActiveId, onKeyDown };
}
