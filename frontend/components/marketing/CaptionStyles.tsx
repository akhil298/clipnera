'use client';

import { useState } from 'react';

import { Badge } from '@/components/ui';
import { cx, focusRing } from '@/lib/design/styles';
import { LANDING_CLIPS } from '@/lib/landingMedia';
import { getAllCaptionStyles, getCaptionStyle, type CaptionPreset } from '@/lib/utils/captionStyles';

import { CaptionSample } from './CaptionSample';

/** Featured styles; each comes from the same catalogue the export renders with. */
const FEATURED: CaptionPreset[] = ['karaoke', 'purple_pop', 'glitch', 'blur_in'];
const PHONE_WORDS = ['Watch', 'this', 'part'];
const CARD_WORDS = ['This', 'changes', 'everything'];
const OPTIONS = ['Auto-emoji on or off', 'Uppercase', 'One or two lines', 'Your own colours'];
const STYLE_COUNT = getAllCaptionStyles().length;
const clip = LANDING_CLIPS.talk;

/** Pick a real caption style and the phone restyles with its font, colours, casing and motion. */
export function CaptionStyles() {
  const [preset, setPreset] = useState<CaptionPreset>('karaoke');
  const current = getCaptionStyle(preset);

  return (
    <div className="grid items-start gap-10 lg:grid-cols-5">
      <div data-theme="dark" className="relative mx-auto w-full max-w-xs overflow-hidden rounded-cn-2xl bg-cn-stage shadow-cn-3 aspect-cn-portrait lg:col-span-2">
        <img src={clip.poster} alt={clip.alt} loading="lazy" decoding="async" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-x-3 bottom-1/4">
          <CaptionSample key={preset} config={current.config} words={PHONE_WORDS} fontSize={30} />
        </div>
        <span className="absolute left-3 top-3 rounded-cn-xs bg-cn-stage/80 px-1.5 text-cn-caption text-cn-fg">Preview · {current.brandName}</span>
      </div>

      <div className="flex flex-col gap-6 lg:col-span-3">
        <div role="group" aria-label="Caption style" className="grid gap-3 sm:grid-cols-2">
          {FEATURED.map((id) => {
            const style = getCaptionStyle(id);
            const active = id === preset;
            return (
              <button
                key={id}
                type="button"
                aria-pressed={active}
                onClick={() => setPreset(id)}
                className={cx(
                  'flex flex-col gap-3 rounded-cn-lg border bg-cn-surface p-4 text-left transition-colors duration-cn-fast ease-cn-standard hover:bg-cn-surface-hover active:bg-cn-surface-active',
                  active ? 'border-cn-accent-border ring-1 ring-cn-accent-border' : 'border-cn-border',
                  focusRing,
                )}
              >
                <span data-theme="dark" className="flex h-16 items-center justify-center overflow-hidden rounded-cn-md bg-cn-stage px-2">
                  <CaptionSample config={style.config} words={CARD_WORDS} fontSize={18} />
                </span>
                <span className="text-cn-body font-semibold text-cn-fg">{style.brandName}</span>
                <span className="text-cn-label text-cn-fg-secondary">{style.description}</span>
              </button>
            );
          })}
        </div>
        <ul aria-label="Every style lets you change" className="flex flex-wrap gap-2">
          {OPTIONS.map((option) => (
            <li key={option}>
              <Badge>{option}</Badge>
            </li>
          ))}
          <li>
            <Badge tone="accent">Brand kit with your logo · Pro</Badge>
          </li>
        </ul>
        <p className="text-cn-label text-cn-fg-muted">
          {STYLE_COUNT} styles in all, in English, Hindi, Telugu, Hinglish and Tenglish.
        </p>
      </div>
    </div>
  );
}
