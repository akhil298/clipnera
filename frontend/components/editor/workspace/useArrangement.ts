'use client';

import { useSyncExternalStore } from 'react';

import { breakpoint } from '@/lib/design/tokens';

/** The editor's default arrangements by width (07 §5.4, §5.7). */
export type Arrangement = 'wide' | 'xl' | 'lg' | 'md' | 'phone';

const STEPS: ReadonlyArray<[Arrangement, number]> = [
  ['wide', breakpoint.wide],
  ['xl', breakpoint.xl],
  ['lg', breakpoint.lg],
  ['md', breakpoint.md],
];

const query = (min: number) => window.matchMedia(`(min-width: ${min}px)`);

function current(): Arrangement {
  return STEPS.find(([, min]) => query(min).matches)?.[0] ?? 'phone';
}

function subscribe(onChange: () => void): () => void {
  const lists = STEPS.map(([, min]) => query(min));
  lists.forEach((list) => list.addEventListener('change', onChange));
  return () => lists.forEach((list) => list.removeEventListener('change', onChange));
}

/** Which arrangement the window is in now; `wide` on the server. */
export function useArrangement(): Arrangement {
  return useSyncExternalStore(subscribe, current, () => 'wide');
}
