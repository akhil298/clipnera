'use client';

import React from 'react';
import { Sparkles } from 'lucide-react';
import type { PremiumResponse } from '@/lib/api';
import { AUDIO_NAMES, PREMIUM_LAYERS, RECIPE_NAMES } from '@/lib/utils/footageReels';

const scoreTone = (score: number) => (score >= 8 ? 'bg-emerald-400' : score >= 6 ? 'bg-amber-400' : 'bg-rose-400');

/** How the reel engine edited the reel: what it decided, how the head-editor review scored each layer, what it made. */
export function PremiumReelReport({ premium }: { premium: PremiumResponse }) {
  const made = premium.assets.filter((a) => a.made);
  const facts: [string, string][] = [
    ['Style', premium.recipe ? RECIPE_NAMES[premium.recipe] ?? premium.recipe : '—'],
    ['Audio', premium.audio_kind ? AUDIO_NAMES[premium.audio_kind] ?? premium.audio_kind : '—'],
    ['Shots', String(premium.shots)],
    ['Graphics', String(premium.graphics)],
    ['Caption lines', String(premium.captions)],
    ['Review passes', String(premium.passes)],
  ];

  return (
    <div className="space-y-5">
      <div className="rounded-[22px] border border-neutral-800 bg-neutral-900/80 p-5 sm:px-6 space-y-4">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="text-base font-semibold text-white">Head-editor review</h3>
          <span className="font-mono text-2xl font-bold text-amber-300 tabular-nums">{premium.overall.toFixed(1)}<span className="text-base text-neutral-500">/10</span></span>
        </div>
        <ul className="grid gap-x-6 gap-y-2.5 sm:grid-cols-2">
          {premium.scores.map((s) => (
            <li key={s.layer} className="min-w-0" title={s.note}>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="text-neutral-200">{PREMIUM_LAYERS[s.layer] ?? s.layer}</span>
                <span className="font-mono tabular-nums text-neutral-300">{s.score}</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-neutral-800 overflow-hidden" aria-hidden="true">
                <div className={`h-full rounded-full ${scoreTone(s.score)}`} style={{ width: `${s.score * 10}%` }} />
              </div>
            </li>
          ))}
        </ul>
        {premium.fixes.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[13px] font-semibold text-neutral-400">What it would still improve</p>
            <ul className="list-disc pl-5 space-y-1 text-[14px] text-neutral-300">
              {premium.fixes.map((fix) => <li key={fix}>{fix}</li>)}
            </ul>
          </div>
        )}
      </div>

      <div className="rounded-[22px] border border-neutral-800 bg-neutral-900/80 p-5 sm:px-6 space-y-4">
        <h3 className="text-base font-semibold text-white">How it was edited</h3>
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-3">
          {facts.map(([term, value]) => (
            <div key={term} className="min-w-0">
              <dt className="text-[12px] uppercase tracking-wide text-neutral-500">{term}</dt>
              <dd className="text-[15px] text-neutral-100 break-words">{value}</dd>
            </div>
          ))}
        </dl>
        {premium.audio_why && <p className="text-[13px] text-neutral-400">{premium.audio_why}</p>}
        {premium.sections.length > 0 && (
          <div className="flex flex-wrap gap-2" aria-label="Chapters">
            {premium.sections.map((section, i) => (
              <span key={section} className="h-8 inline-flex items-center gap-2 px-3 rounded-full bg-neutral-800 text-[13px] font-semibold text-neutral-200">
                <span className="font-mono text-amber-300">{String(i + 1).padStart(2, '0')}</span> {section}
              </span>
            ))}
          </div>
        )}
        {made.length > 0 && (
          <p className="flex items-start gap-2 text-[13px] text-neutral-300">
            <Sparkles className="w-4 h-4 text-amber-300 shrink-0 mt-0.5" />
            Made {made.length} new asset{made.length === 1 ? '' : 's'} for this reel ({Array.from(new Set(made.map((a) => a.kind))).join(', ')}) and added them to your library.
          </p>
        )}
      </div>
    </div>
  );
}
