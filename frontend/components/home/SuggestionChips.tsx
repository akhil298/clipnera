'use client';

import { Sparkles } from 'lucide-react';

import { Chip } from '@/components/ui';

/** Four starters under the composer. A click fills the box; it never sends. */
export function SuggestionChips({ items, onPick }: { items: readonly string[]; onPick: (text: string) => void }) {
  return (
    <ul
      aria-label="Suggestions"
      className="flex max-w-full gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:justify-center sm:overflow-visible"
    >
      {items.map((item) => (
        <li key={item} className="shrink-0">
          <Chip icon={<Sparkles aria-hidden />} onClick={() => onPick(item)}>
            {item}
          </Chip>
        </li>
      ))}
    </ul>
  );
}
