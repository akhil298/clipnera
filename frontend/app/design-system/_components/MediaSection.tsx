'use client';

import { Film, Lock } from 'lucide-react';
import { useState } from 'react';

import { Badge, Button, cardLinkOverlay, Checkbox, EmptyState, MediaGrid, VideoThumb } from '@/components/ui';
import { cx, focusWithinRing } from '@/lib/design/styles';

import { GallerySection, Specimen, State, StateGrid } from './Specimen';

interface SampleClip {
  id: string;
  title: string;
  duration: number;
  score: number;
}

const CLIPS: ReadonlyArray<SampleClip> = [
  { id: 'c1', title: 'Pricing is a product decision', duration: 42, score: 91 },
  { id: 'c2', title: 'Why we fired our best customer', duration: 58, score: 78 },
  { id: 'c3', title: 'The first ten hires', duration: 31, score: 64 },
  { id: 'c4', title: 'Raising without a deck', duration: 74, score: 86 },
  { id: 'c5', title: 'What I would do differently', duration: 49, score: 72 },
];

/** A clip tile composed from VideoThumb: one real button covers the card; the checkbox sits above it. */
function ClipTile({ clip, selected, onToggle }: { clip: SampleClip; selected: boolean; onToggle: () => void }) {
  return (
    <div className={cx('group relative flex flex-col gap-1.5 rounded-cn-md', focusWithinRing)}>
      <VideoThumb
        duration={clip.duration}
        score={clip.score}
        selected={selected}
        topLeft={<Checkbox className="relative z-cn-raised" checked={selected} onChange={onToggle} label={<span className="sr-only">Select {clip.title}</span>} />}
      />
      <button type="button" className={cx('text-left', cardLinkOverlay)}>
        <span className="line-clamp-2 text-cn-label font-semibold text-cn-fg">{clip.title}</span>
      </button>
    </div>
  );
}

export function MediaSection() {
  const [scrub, setScrub] = useState<number | null>(null);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set(['c1']));
  const [state, setState] = useState<'full' | 'loading' | 'empty'>('full');

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <GallerySection id="media" title="Media" intro="Posters and grids. The player chrome and timeline stay with the Editor screens (02 §5.1–5.2).">
      <Specimen title="VideoThumb" note="Duration and score chips on the poster; missing posters show the film tile. Hover preview plays a muted proxy after 150 ms, never under reduced motion.">
        <StateGrid className="lg:grid-cols-5">
          <State label="9:16 with score" className="w-full">
            <VideoThumb duration={42} score={91} className="w-full" />
          </State>
          <State label="selected" className="w-full">
            <VideoThumb duration={58} score={74} selected className="w-full" />
          </State>
          <State label="dimmed + badge" className="w-full">
            <VideoThumb duration={31} dimmed topLeft={<Badge icon={<Lock />}>Licence ended</Badge>} className="w-full" />
          </State>
          <State label={`scrub hook ${scrub === null ? '' : `${Math.round(scrub * 100)}%`}`} className="w-full">
            <VideoThumb duration={120} onScrub={setScrub} className="w-full" />
          </State>
          <State label="16:9" className="col-span-2 w-full lg:col-span-1">
            <VideoThumb aspect="16:9" duration={3725} className="w-full" />
          </State>
        </StateGrid>
      </Specimen>

      <Specimen title="MediaGrid" note="Responsive columns by aspect; arrows move between tiles; skeleton tiles in one live region; EmptyState when there is nothing.">
        <div className="mb-4 flex flex-wrap gap-2">
          {(['full', 'loading', 'empty'] as const).map((option) => (
            <Button key={option} size="sm" variant={state === option ? 'primary' : 'secondary'} onClick={() => setState(option)}>
              {option}
            </Button>
          ))}
        </div>
        <MediaGrid
          label="Clips"
          items={state === 'full' ? CLIPS : []}
          getKey={(clip) => clip.id}
          loading={state === 'loading'}
          skeletonCount={5}
          empty={<EmptyState size="compact" level={3} icon={<Film />} title="No clips yet" description="Clips appear here as soon as Clipnera finds moments." />}
          renderItem={(clip) => <ClipTile clip={clip} selected={selected.has(clip.id)} onToggle={() => toggle(clip.id)} />}
        />
      </Specimen>
    </GallerySection>
  );
}
