'use client';

import { Search, Shuffle } from 'lucide-react';
import { useId, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';

import { MediaCard, Poster } from './MediaCard';
import { BROLL_ALTERNATES } from './sample';

export interface Pick {
  title: string;
  source: string;
  range: string;
  reasons: string[];
}

/**
 * The "chose this clip because…" line under a B-roll result (05-broll §8.3),
 * with one-click swap: Swap opens four alternates with hover preview; one
 * click on an alternate swaps it as one new version. "Search for something
 * else" hands over to the Library panel (owned by the library screens).
 */
export function BrollPick({ pick, onOpenLibrary }: { pick: Pick; onOpenLibrary?: (query: string) => void }) {
  const id = useId();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(pick.title);

  const swap = (title: string) => {
    setCurrent(title);
    setOpen(false);
    toast.show({ title: `Swapped B-roll at ${pick.range.split(' ')[0]}`, description: `Now “${title}”. Saved as a new version.`, action: { label: 'Undo', onClick: () => setCurrent(pick.title) } });
  };

  return (
    <div className="ml-7 flex flex-col gap-2 rounded-cn-md border border-cn-border bg-cn-surface p-2.5">
      <div className="flex items-start gap-2.5">
        <Poster tone={5} className="w-10 shrink-0 rounded-cn-sm" />
        <div className="min-w-0 space-y-0.5">
          <p className="text-cn-label text-cn-fg">
            “{current}” <span className="text-cn-fg-muted">at {pick.range} · from {pick.source}</span>
          </p>
          <p className="text-cn-caption text-cn-fg-secondary">
            <span className="font-semibold">Chose this because</span> it {pick.reasons.join(' · ')}.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" leadingIcon={<Shuffle />} aria-expanded={open} aria-controls={`${id}-alternates`} onClick={() => setOpen(!open)}>
          Swap
        </Button>
        {onOpenLibrary && (
          <Button size="sm" variant="ghost" leadingIcon={<Search />} onClick={() => onOpenLibrary('coffee pour')}>
            Search for something else
          </Button>
        )}
      </div>
      {open && (
        <ul id={`${id}-alternates`} aria-label="Other shots that fit" className="grid grid-cols-4 gap-2">
          {BROLL_ALTERNATES.map((shot) => (
            <li key={shot.id}>
              <MediaCard size="sm" title={shot.title} length={shot.length} tone={shot.tone} meta={shot.source} actionLabel={`Use ${shot.title}`} onOpen={() => swap(shot.title)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
