'use client';

import { useState } from 'react';
import { ChevronsLeftRight } from 'lucide-react';
import { LandingVideo } from './LandingVideo';
import { BurnedCaption } from './BurnedCaption';
import { SectionIntro } from './SectionIntro';

const DIFFERENCES = [
  { aspect: 'Framing', raw: 'Centre crop, speaker half out of shot', clipnera: 'Crop follows the speaker' },
  { aspect: 'Audio', raw: 'Fan hum and room echo', clipnera: 'Steady noise reduced, voice evened out' },
  { aspect: 'Captions', raw: 'None', clipnera: 'Word-by-word, styled, burned in' },
  { aspect: 'Length', raw: 'The full 46-minute interview', clipnera: 'A 44-second clip that opens on the hook' },
  { aspect: 'Posting', raw: 'Write your own title', clipnera: 'Suggested title and hashtags, editable' },
];

const chip = 'absolute px-2.5 py-1 font-jetbrains text-[10px]';

/** One phone, two versions of the same moment, and a divider to drag between them. */
export function BeforeAfterShowcase() {
  const [split, setSplit] = useState(45);

  return (
    <section id="before-after" className="scroll-mt-20 py-20 lg:py-24">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-14 px-4 sm:px-8 lg:flex-row lg:items-start lg:justify-between lg:gap-12 xl:px-16">
        <div className="space-y-8 lg:max-w-[880px] lg:flex-1">
          <SectionIntro eyebrow="04 · Before / after" title={<>Drag the line.<br />That's the whole edit.</>}>
            Left of the line is what a plain vertical export gives you. Right of it is the same moment after Clipnera.
          </SectionIntro>

          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left font-jetbrains text-[11px] tracking-[0.1em] text-neutral-500">
                <th className="pb-3 font-medium">
                  <span className="sr-only">Aspect</span>
                </th>
                <th className="pb-3 font-medium">RAW EXPORT</th>
                <th className="pb-3 font-medium text-amber-400">CLIPNERA</th>
              </tr>
            </thead>
            <tbody>
              {DIFFERENCES.map((row) => (
                <tr key={row.aspect} className="border-t border-neutral-800">
                  <th scope="row" className="w-28 py-3.5 text-left font-bold text-neutral-200">
                    {row.aspect}
                  </th>
                  <td className="py-3.5 pr-4 text-neutral-500">{row.raw}</td>
                  <td className="py-3.5 text-white">{row.clipnera}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mx-auto w-full max-w-[380px] flex-shrink-0 space-y-5">
          <div className="relative aspect-[380/676] overflow-hidden rounded-[34px] border border-neutral-700 shadow-[0_40px_80px_rgba(0,0,0,0.6)]">
            <LandingVideo clip="interview" position="30% 40%" className="absolute inset-0">
              <div className="absolute inset-x-0 bottom-0 h-[45%] bg-gradient-to-b from-transparent to-black/75" />
              <BurnedCaption lines={['I almost quit', 'that year']} highlight="quit" className="absolute inset-x-4 bottom-[22%] text-[30px]" />
              <span className={`${chip} right-4 top-4 rounded-full bg-amber-500 font-bold text-neutral-950`}>AFTER</span>
              <span className={`${chip} bottom-5 right-4 rounded-lg bg-neutral-950/80 text-neutral-200`}>VOICE CLEANED · 0:44</span>
            </LandingVideo>

            <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
              <LandingVideo clip="interview" position="50% 40%" className="absolute inset-0" mediaClassName="saturate-[0.6] brightness-[0.8]">
                <span className={`${chip} left-4 top-4 rounded-full bg-neutral-950/80 font-bold text-neutral-200`}>BEFORE</span>
                <span className={`${chip} bottom-5 left-4 rounded-lg bg-neutral-950/80 text-neutral-400`}>CENTRE CROP · HUM · 46:30</span>
              </LandingVideo>
            </div>

            <div className="pointer-events-none absolute inset-y-0 w-0.5 -translate-x-1/2 bg-white" style={{ left: `${split}%` }}>
              <span className="absolute left-1/2 top-1/2 flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white text-neutral-950 shadow-lg">
                <ChevronsLeftRight className="h-[18px] w-[18px]" aria-hidden="true" />
              </span>
            </div>
          </div>

          <label className="block space-y-2 text-[13px] text-neutral-400">
            <span>Compare before and after</span>
            <input
              type="range"
              min={0}
              max={100}
              value={split}
              onChange={(e) => setSplit(Number(e.target.value))}
              className="h-11 w-full cursor-ew-resize accent-amber-500"
            />
          </label>
        </div>
      </div>
    </section>
  );
}
