'use client';

import React from 'react';
import { Coins, Crop, Sparkles } from 'lucide-react';
import type { AspectRatio } from '@/lib/types';
import {
  canUseAspectRatio,
  canUseFeature,
  estimateVideoCredits,
  useEntitlements,
} from '@/hooks/useEntitlements';
import { ProLockBadge } from './ProLockBadge';

interface OutputFormat {
  ratio: AspectRatio;
  name: string;
  platforms: string;
  /** Tailwind size of the shape glyph, drawn at the format's proportions. */
  glyph: string;
}

/** Every format the renderer supports, tallest first; see SUPPORTED_ASPECT_RATIOS in video_processor/geometry.py. */
const OUTPUT_FORMATS: OutputFormat[] = [
  { ratio: '9:16', name: 'Vertical', platforms: 'Shorts · TikTok · Reels', glyph: 'w-[9px] h-4' },
  { ratio: '4:5', name: 'Portrait', platforms: 'Instagram & Facebook feed', glyph: 'w-3 h-[15px]' },
  { ratio: '1:1', name: 'Square', platforms: 'Feeds · LinkedIn · X', glyph: 'w-3.5 h-3.5' },
  { ratio: '16:9', name: 'Landscape', platforms: 'YouTube · Web', glyph: 'w-4 h-[9px]' },
];

interface OutputFormatPickerProps {
  /** Picked ratios; empty means the pipeline picks from the content category. */
  value: AspectRatio[];
  onChange: (ratios: AspectRatio[]) => void;
  /** Source length, for the cost estimate; null until the video's metadata loads. */
  durationSeconds: number | null;
}

/**
 * Which shapes each clip is rendered in. Choosing is a Pro feature; every plan
 * gets Auto. The server enforces the same rules and charges the cost shown.
 */
export function OutputFormatPicker({ value, onChange, durationSeconds }: OutputFormatPickerProps) {
  const { entitlements, promptUpgrade } = useEntitlements();
  const canChoose = canUseFeature(entitlements, 'custom_aspect_ratios');
  const isAuto = value.length === 0;

  const toggle = (ratio: AspectRatio) => {
    if (!canChoose || !canUseAspectRatio(entitlements, ratio)) {
      promptUpgrade(`The ${ratio} format`);
      return;
    }
    const next = value.includes(ratio) ? value.filter((r) => r !== ratio) : [...value, ratio];
    // Keep the canonical order so the request and the cost line read the same way every time.
    onChange(OUTPUT_FORMATS.map((f) => f.ratio).filter((r) => next.includes(r)));
  };

  const ratioCount = Math.max(1, value.length);
  const extraShare = Math.round(entitlements.extra_aspect_ratio_credit_share * 100);

  return (
    <div className="border-t border-neutral-800/80 pt-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
          <Crop className="w-4 h-4 text-amber-400" />
          <span>Output Formats</span>
        </h3>
        {!canChoose && <ProLockBadge feature="Choosing output formats" />}
      </div>

      <button
        type="button"
        onClick={() => onChange([])}
        aria-pressed={isAuto}
        className={`w-full flex items-center justify-between p-3 rounded-xl border text-left transition-all ${
          isAuto
            ? 'bg-neutral-800 border-amber-400 ring-1 ring-amber-400/30'
            : 'bg-neutral-950 border-neutral-800 hover:border-neutral-700'
        }`}
      >
        <span className="flex items-center gap-2.5">
          <Sparkles className="w-4 h-4 text-amber-400" />
          <span>
            <span className="text-xs font-bold text-white block">Auto</span>
            <span className="text-[10px] text-neutral-400">
              Formats that suit the video&apos;s content, at the base price
            </span>
          </span>
        </span>
      </button>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" role="group" aria-label="Output formats">
        {OUTPUT_FORMATS.map((format) => {
          const unlocked = canChoose && canUseAspectRatio(entitlements, format.ratio);
          const selected = value.includes(format.ratio);
          return (
            <button
              key={format.ratio}
              type="button"
              onClick={() => toggle(format.ratio)}
              aria-pressed={selected}
              aria-disabled={!unlocked}
              className={`relative p-2.5 rounded-xl border text-left transition-all ${
                selected
                  ? 'bg-neutral-800 border-amber-400 ring-1 ring-amber-400/30'
                  : unlocked
                  ? 'bg-neutral-950 border-neutral-800 hover:border-neutral-700'
                  : 'bg-neutral-950/60 border-neutral-800/60 opacity-70 hover:border-amber-400/40 hover:opacity-100'
              }`}
            >
              <span className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 flex items-center justify-center">
                    <span
                      className={`${format.glyph} rounded-[2px] border ${
                        selected ? 'border-amber-400 bg-amber-400/20' : 'border-neutral-500'
                      }`}
                    />
                  </span>
                  <span className="text-xs font-bold text-white">{format.ratio}</span>
                </span>
                {!unlocked && <ProLockBadge feature={`The ${format.ratio} format`} />}
              </span>
              <span className="mt-1.5 block text-[11px] font-semibold text-neutral-200">{format.name}</span>
              <span className="block text-[10px] text-neutral-400 truncate">{format.platforms}</span>
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-3 rounded-xl bg-neutral-950 border border-neutral-800 px-3 py-2">
        <span className="flex items-center gap-2 text-[11px] text-neutral-400">
          <Coins className="w-3.5 h-3.5 text-amber-400" />
          {canChoose
            ? `Base ${entitlements.credits_per_video_minute} credits/min, first format included · +${extraShare}% per extra format`
            : `${entitlements.credits_per_video_minute} credits per video minute`}
        </span>
        {durationSeconds ? (
          <span className="text-xs font-bold text-amber-300 shrink-0">
            {estimateVideoCredits(entitlements, durationSeconds, ratioCount)} credits
          </span>
        ) : null}
      </div>
    </div>
  );
}
