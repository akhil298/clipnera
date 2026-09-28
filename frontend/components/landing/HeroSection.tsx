'use client';

import { useState } from 'react';
import { Upload, Wand2 } from 'lucide-react';
import { VideoLinkForm } from './VideoLinkForm';
import { HeroStage } from './HeroStage';

interface HeroSectionProps {
  heroUrl: string;
  setHeroUrl: (url: string) => void;
  onLaunchStudio: () => void;
}

type SourceMode = 'link' | 'upload' | 'prompt';

const SOURCE_MODES: Array<{ id: SourceMode; label: string }> = [
  { id: 'link', label: 'YouTube link' },
  { id: 'upload', label: 'Upload a file' },
  { id: 'prompt', label: 'Write a prompt' },
];

const PROMISES = ['Free plan, no card', 'Free credits every 30 days', 'Background noise reduction'];

export function HeroSection({ heroUrl, setHeroUrl, onLaunchStudio }: HeroSectionProps) {
  const [mode, setMode] = useState<SourceMode>('link');

  return (
    <section className="relative overflow-hidden pb-20 pt-10 lg:pt-12">
      <div className="mx-auto max-w-[1440px] space-y-10 px-4 sm:px-8 xl:px-16">
        <header className="space-y-7">
          <div className="space-y-5">
            <p className="flex items-center gap-2.5 font-jetbrains text-xs font-medium uppercase tracking-[0.14em] text-amber-400">
              <span aria-hidden="true" className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
              Live demo · real footage, real output
            </p>
            <h1 className="font-syne text-[44px] font-extrabold leading-[0.98] tracking-[-0.035em] text-white sm:text-6xl lg:text-6xl xl:text-[76px]">
              One long video in.
              <br />A week of <span className="text-amber-500">Shorts</span> out.
            </h1>
          </div>

          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between lg:gap-16">
            <div className="max-w-[600px] space-y-3.5">
              <p className="text-base leading-relaxed text-neutral-300 sm:text-[17px]">
                Clipnera finds the moments worth posting, reframes them to 9:16 around the speaker, cleans the audio and
                burns in word-by-word captions. You review, then publish.
              </p>
              <ul className="flex flex-wrap gap-x-5 gap-y-2 text-[13px] text-neutral-400">
                {PROMISES.map((promise) => (
                  <li key={promise}>
                    <span aria-hidden="true" className="text-emerald-400">✓ </span>
                    {promise}
                  </li>
                ))}
              </ul>
            </div>

            <div className="w-full space-y-2.5 lg:w-[560px] lg:flex-shrink-0">
              <div role="group" aria-label="How to add your video" className="flex flex-wrap gap-1.5">
                {SOURCE_MODES.map(({ id, label }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setMode(id)}
                    aria-pressed={mode === id}
                    className={`h-9 rounded-[10px] border px-3.5 text-[13px] transition-colors ${
                      mode === id
                        ? 'border-amber-900 bg-amber-950/60 font-bold text-amber-300'
                        : 'border-neutral-800 font-semibold text-neutral-300 hover:text-white'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {mode === 'link' && <VideoLinkForm id="hero-url" url={heroUrl} setUrl={setHeroUrl} onSubmit={onLaunchStudio} />}
              {mode === 'upload' && (
                <button
                  type="button"
                  onClick={onLaunchStudio}
                  className="flex h-[62px] w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-neutral-700 bg-neutral-900 text-[15px] font-bold text-white transition-colors hover:border-amber-500"
                >
                  <Upload className="h-4 w-4 text-amber-400" aria-hidden="true" />
                  Choose a video file
                </button>
              )}
              {mode === 'prompt' && (
                <button
                  type="button"
                  onClick={onLaunchStudio}
                  className="flex h-[62px] w-full items-center justify-center gap-2 rounded-2xl border border-neutral-800 bg-neutral-900 text-[15px] font-bold text-white transition-colors hover:border-amber-500"
                >
                  <Wand2 className="h-4 w-4 text-amber-400" aria-hidden="true" />
                  Turn a story idea into a Short
                </button>
              )}
            </div>
          </div>
        </header>

        <HeroStage />
      </div>
    </section>
  );
}
