'use client';

import { useState } from 'react';
import { getAllCaptionStyles, getCaptionStyle, type CaptionPreset } from '@/lib/utils/captionStyles';
import { CaptionStylePreview } from '@/components/dashboard/CaptionStylePreview';
import { LandingVideo } from './LandingVideo';

// Featured presets; every one comes from the same list the export renders with.
const FEATURED: CaptionPreset[] = ['bold_pop', 'karaoke_yellow', 'cyberpunk', 'neon'];
const PHONE_WORDS = ['Watch', 'this', 'part'];

const OPTIONS = ['Auto-emoji on/off', 'UPPERCASE', '1 or 2 lines', 'Custom colours'];

/** Pick a real caption preset and the phone re-styles with its colours, font, casing and motion. */
export function CaptionTypographyShowcase() {
  const [preset, setPreset] = useState<CaptionPreset>('bold_pop');
  const { config, brandName } = getCaptionStyle(preset);
  const presetCount = getAllCaptionStyles().length;

  return (
    <section id="captions" className="scroll-mt-20 py-20 lg:py-24">
      <div className="mx-auto flex max-w-[1440px] flex-col-reverse items-center gap-14 px-4 sm:px-8 lg:flex-row lg:items-start lg:gap-24 xl:px-16">
        <LandingVideo
          clip="talk"
          className="relative aspect-[340/604] w-full max-w-[340px] flex-shrink-0 rounded-[30px] border border-neutral-700 shadow-[0_40px_80px_rgba(0,0,0,0.6)]"
        >
          <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-b from-transparent to-black/60" />
          <div className="absolute inset-x-3 bottom-[22%]">
            <CaptionStylePreview key={preset} config={config} words={PHONE_WORDS} fontSize={30} overlay />
          </div>
          <span className="absolute left-4 top-4 rounded-lg bg-neutral-950/80 px-2.5 py-1 font-jetbrains text-[10px] text-neutral-200">
            PREVIEW · {brandName}
          </span>
        </LandingVideo>

        <div className="w-full space-y-7">
          <div className="space-y-4">
            <p className="font-jetbrains text-xs font-medium uppercase tracking-[0.14em] text-amber-400">05 · Captions</p>
            <h2 className="font-syne text-[28px] font-extrabold leading-none tracking-[-0.03em] text-white sm:text-5xl lg:text-[54px]">
              Captions people
              <br />
              actually read.
            </h2>
            <p className="max-w-[560px] text-base leading-relaxed text-neutral-300">
              Most Shorts are watched on mute. Pick a style and the phone updates. {presetCount} presets, and every one lets you
              change colours, casing, line count and auto-emoji.
            </p>
          </div>

          <div role="group" aria-label="Caption style" className="grid max-w-[760px] gap-4 sm:grid-cols-2">
            {FEATURED.map((id) => {
              const style = getCaptionStyle(id);
              const active = id === preset;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPreset(id)}
                  aria-pressed={active}
                  className={`flex flex-col gap-3 rounded-[18px] border-2 bg-[#121212] p-4 text-left transition-colors ${
                    active ? 'border-amber-500' : 'border-neutral-800 hover:border-neutral-600'
                  }`}
                >
                  <CaptionStylePreview config={style.config} className="h-14 w-full" />
                  <span className="text-[15px] font-bold text-white">{style.brandName}</span>
                  <span className="text-[13px] leading-snug text-neutral-400">{style.description}</span>
                </button>
              );
            })}
          </div>

          <ul className="flex max-w-[760px] flex-wrap gap-2.5 text-[13px] text-neutral-300">
            {OPTIONS.map((option) => (
              <li key={option} className="rounded-full border border-neutral-800 px-3 py-2">
                {option}
              </li>
            ))}
            <li className="rounded-full border border-amber-900 px-3 py-2 text-amber-300">Brand kit with your logo · Pro</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
