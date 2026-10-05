'use client';

import { ChevronsLeftRight } from 'lucide-react';
import { useState } from 'react';

import { LANDING_CLIPS } from '@/lib/landingMedia';

import { BurnedCaption } from './BurnedCaption';

const DIFFERENCES = [
  { aspect: 'Framing', raw: 'Centre crop, speaker half out of shot', clipnera: 'Crop follows the speaker' },
  { aspect: 'Audio', raw: 'Fan hum and room echo', clipnera: 'Steady noise reduced, voice evened out' },
  { aspect: 'Captions', raw: 'None', clipnera: 'Word by word, styled, burned in' },
  { aspect: 'Length', raw: 'The full 46-minute interview', clipnera: 'A 44-second clip that opens on the hook' },
  { aspect: 'Posting', raw: 'Write your own title', clipnera: 'Suggested title and hashtags, editable' },
];

const TAG = 'absolute rounded-cn-xs bg-cn-stage/80 px-1.5 font-cn-mono text-cn-caption text-cn-fg';
const clip = LANDING_CLIPS.interview;

/** One phone, two versions of the same moment, and a divider to drag (or arrow-key) between them. */
export function BeforeAfter() {
  const [split, setSplit] = useState(45);

  return (
    <div className="grid items-center gap-10 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <table className="w-full border-collapse text-cn-body">
          <caption className="sr-only">What changes between a plain vertical export and a Clipnera clip</caption>
          <thead>
            <tr className="text-left text-cn-label text-cn-fg-muted">
              <th scope="col" className="pb-3 font-medium">
                <span className="sr-only">Aspect</span>
              </th>
              <th scope="col" className="pb-3 font-medium">Plain export</th>
              <th scope="col" className="pb-3 font-medium text-cn-fg">Clipnera</th>
            </tr>
          </thead>
          <tbody>
            {DIFFERENCES.map((row) => (
              <tr key={row.aspect} className="border-t border-cn-border align-top">
                <th scope="row" className="w-24 py-3 pr-3 text-left font-semibold text-cn-fg">
                  {row.aspect}
                </th>
                <td className="py-3 pr-4 text-cn-fg-muted">{row.raw}</td>
                <td className="py-3 text-cn-fg">{row.clipnera}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div data-theme="dark" className="relative mx-auto w-full max-w-xs overflow-hidden rounded-cn-2xl bg-cn-stage shadow-cn-3 aspect-cn-portrait lg:col-span-2">
        <img src={clip.poster} alt={clip.alt} loading="lazy" decoding="async" className="absolute inset-0 h-full w-full object-cover object-left" />
        <BurnedCaption lines={['I almost quit', 'that year']} highlight="quit" className="absolute inset-x-4 bottom-1/4 text-cn-title-lg" />
        <span className={`${TAG} right-3 top-3`}>After</span>
        <span className={`${TAG} bottom-3 right-3`}>Voice cleaned · 0:44</span>

        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
          <img src={clip.poster} alt="" loading="lazy" decoding="async" className="absolute inset-0 h-full w-full object-cover brightness-75 saturate-50" />
          <span className={`${TAG} left-3 top-3`}>Before</span>
          <span className={`${TAG} bottom-3 left-3`}>Centre crop · hum · 46:30</span>
        </div>

        <input
          type="range"
          min={0}
          max={100}
          value={split}
          onChange={(event) => setSplit(Number(event.target.value))}
          aria-label="Compare before and after"
          aria-valuetext={`${split}% before, ${100 - split}% after`}
          className="peer absolute inset-0 z-cn-raised m-0 h-full w-full cursor-ew-resize touch-pan-y appearance-none bg-transparent opacity-0"
        />
        <div aria-hidden className="pointer-events-none absolute inset-y-0 w-0.5 -translate-x-1/2 bg-cn-fg" style={{ left: `${split}%` }}>
          <span className="absolute left-1/2 top-1/2 flex size-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-cn-full bg-cn-fg text-cn-bg shadow-cn-2">
            <ChevronsLeftRight className="size-4" />
          </span>
        </div>
        <span aria-hidden className="pointer-events-none absolute inset-0 hidden rounded-cn-2xl ring-2 ring-inset ring-cn-focus peer-focus-visible:block" />
      </div>
    </div>
  );
}
