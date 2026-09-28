'use client';

import { useRef, useState } from 'react';
import { ArrowRight, ChevronLeft, ChevronRight } from 'lucide-react';
import type { LandingClipKey } from '@/lib/landingMedia';
import { LandingVideo } from './LandingVideo';
import { BurnedCaption } from './BurnedCaption';
import { SectionIntro } from './SectionIntro';

const CATEGORIES = ['All', 'Podcasts', 'Interviews', 'Talking head', 'Cooking', 'Streams', 'Vlogs'] as const;
type Category = (typeof CATEGORIES)[number];

const TILES: Array<{
  clip: LandingClipKey;
  category: Exclude<Category, 'All'>;
  position: string;
  score: number;
  lines: string[];
  source: string;
  length: string;
}> = [
  { clip: 'podcast', category: 'Podcasts', position: '72% 50%', score: 94, lines: ['Stop chasing', 'views'], source: '58:12 podcast', length: '0:41' },
  { clip: 'cook', category: 'Cooking', position: '50% 50%', score: 87, lines: ['The step', 'everyone skips'], source: '22:40 recipe', length: '0:29' },
  { clip: 'talk', category: 'Talking head', position: '50% 50%', score: 90, lines: ['Here is the', 'real reason'], source: '14:05 explainer', length: '0:36' },
  { clip: 'interview', category: 'Interviews', position: '40% 50%', score: 89, lines: ['I almost quit', 'that year'], source: '46:30 interview', length: '0:44' },
  { clip: 'stream', category: 'Streams', position: '50% 50%', score: 83, lines: ['Chat went', 'wild here'], source: '2:10:00 stream', length: '0:52' },
  { clip: 'vlog', category: 'Vlogs', position: '50% 50%', score: 79, lines: ['Day one of', 'the challenge'], source: '18:20 vlog', length: '0:31' },
  { clip: 'host', category: 'Podcasts', position: '50% 50%', score: 85, lines: ['Nobody tells', 'you this'], source: '1:04:10 episode', length: '0:38' },
];

const TILE_STEP = 236; // tile width plus gap

interface ClipWallProps {
  onLaunchStudio: () => void;
}

/** A film strip of finished vertical clips, each labelled with the long video it came from. */
export function ClipWall({ onLaunchStudio }: ClipWallProps) {
  const [category, setCategory] = useState<Category>('All');
  const stripRef = useRef<HTMLDivElement>(null);
  const scrollBy = (direction: 1 | -1) => stripRef.current?.scrollBy({ left: direction * TILE_STEP * 2, behavior: 'smooth' });

  return (
    <section id="clip-wall" className="scroll-mt-20 py-20 lg:py-24">
      <div className="mx-auto max-w-[1440px] space-y-9 px-4 sm:px-8 xl:px-16">
        <SectionIntro eyebrow="02 · The clip wall" title={<>Real footage in.<br />Postable clips out.</>} inline>
          Every tile is a finished 9:16 clip, labelled with the long video it was cut from. Pick what you make and see what
          you'd get.
        </SectionIntro>

        <div role="group" aria-label="Filter clips by content type" className="flex flex-wrap gap-2.5">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCategory(c)}
              aria-pressed={category === c}
              className={`h-11 rounded-full border px-[18px] text-sm font-semibold transition-colors ${
                category === c ? 'border-amber-500 bg-amber-500 text-neutral-950' : 'border-neutral-700 text-neutral-200 hover:border-neutral-500'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="relative mt-11 border-y border-neutral-800/80 bg-[#111] py-[50px]">
        {['top-3.5', 'bottom-3.5'].map((edge) => (
          <div
            key={edge}
            aria-hidden="true"
            className={`absolute inset-x-0 ${edge} h-2.5 bg-[repeating-linear-gradient(90deg,transparent_0_12px,#262626_12px_28px,transparent_28px_38px)]`}
          />
        ))}
        <div
          ref={stripRef}
          className="flex snap-x snap-mandatory gap-6 overflow-x-auto px-4 [scrollbar-width:none] sm:px-8 xl:px-16 [&::-webkit-scrollbar]:hidden"
        >
          {TILES.map((tile) => {
            const shown = category === 'All' || tile.category === category;
            return (
              <LandingVideo
                key={tile.clip}
                clip={tile.clip}
                position={tile.position}
                className={`relative h-[378px] w-[212px] flex-shrink-0 snap-start rounded-[18px] border border-neutral-800 transition-[opacity,filter] duration-300 ${
                  shown ? '' : 'opacity-30 grayscale'
                }`}
              >
                <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(0,0,0,0.45)_0%,rgba(0,0,0,0)_25%,rgba(0,0,0,0)_55%,rgba(0,0,0,0.85)_100%)]" />
                <div className="absolute inset-x-3 top-3 flex justify-between font-jetbrains text-[10px] font-bold">
                  <span className="rounded-md bg-neutral-950/75 px-2 py-1 text-neutral-200">{tile.category}</span>
                  <span className="rounded-full bg-amber-500 px-2 py-1 text-neutral-950">{tile.score}</span>
                </div>
                <BurnedCaption lines={tile.lines} className="absolute inset-x-2 bottom-[58px] text-[17px]" />
                <p className="absolute inset-x-3 bottom-3.5 flex items-center gap-1.5 font-jetbrains text-[10px] text-neutral-300">
                  {tile.source}
                  <ArrowRight className="h-3 w-3 text-amber-500" aria-label="cut to" />
                  <span className="text-amber-400">{tile.length} clip</span>
                </p>
              </LandingVideo>
            );
          })}
        </div>
      </div>

      <div className="mx-auto mt-10 flex max-w-[1440px] flex-col gap-4 px-4 sm:flex-row sm:items-center sm:justify-between sm:px-8 xl:px-16">
        <p className="text-sm text-neutral-400">Sample outputs shown for illustration. Your clips come from your own footage.</p>
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => scrollBy(-1)} aria-label="Previous clips" className="flex h-11 w-11 items-center justify-center rounded-full border border-neutral-700 text-white hover:border-neutral-500">
            <ChevronLeft className="h-[18px] w-[18px]" aria-hidden="true" />
          </button>
          <button type="button" onClick={() => scrollBy(1)} aria-label="Next clips" className="flex h-11 w-11 items-center justify-center rounded-full border border-neutral-700 text-white hover:border-neutral-500">
            <ChevronRight className="h-[18px] w-[18px]" aria-hidden="true" />
          </button>
          <button type="button" onClick={onLaunchStudio} className="ml-3 text-sm font-bold text-amber-400 hover:text-amber-300">
            Try it on your video →
          </button>
        </div>
      </div>
    </section>
  );
}
