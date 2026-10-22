'use client';

import React from 'react';
import { Check, Loader2 } from 'lucide-react';
import type { EditResponse } from '@/lib/api';
import { PREMIUM_STEPS, formatSeconds } from '@/lib/utils/footageReels';

/** While the reel engine edits: every stage it has passed, what it found there, and where it is now. */
export function PremiumReelProgress({ edit }: { edit: EditResponse }) {
  const stages = edit.premium?.stages ?? [];
  const notes = Object.fromEntries(stages.map((s) => [s.stage, s.note]));
  const current = stages.length ? stages[stages.length - 1].stage : 'queued';
  const activeIndex = Math.max(0, PREMIUM_STEPS.findIndex(([key]) => key === current));
  const clips = edit.sources.filter((s) => s.kind !== 'reference');

  return (
    <div className="flex flex-wrap gap-6 items-start">
      <section aria-label="Progress" className="flex-[1_1_420px] min-w-0">
        <div className="rounded-[28px] border border-neutral-800 bg-neutral-900/80 p-6 sm:p-7 space-y-6">
          <div className="space-y-1.5">
            <p className="font-mono text-[13px] font-semibold text-amber-300">STEP {activeIndex + 1} OF {PREMIUM_STEPS.length}</p>
            <h2 className="font-syne text-3xl font-extrabold leading-tight text-white" aria-live="polite">
              {current === 'queued' ? 'Waiting to start' : PREMIUM_STEPS[activeIndex][1]}
            </h2>
          </div>
          <div className="h-2 rounded-full bg-neutral-800 overflow-hidden" aria-hidden="true">
            <div className="h-full rounded-full bg-amber-500 transition-[width] duration-700"
              style={{ width: `${((activeIndex + 0.5) / PREMIUM_STEPS.length) * 100}%` }} />
          </div>
          <ol className="space-y-1">
            {PREMIUM_STEPS.map(([key, label], i) => {
              const state = i < activeIndex ? 'done' : i === activeIndex && current !== 'queued' ? 'run' : 'todo';
              return (
                <li key={key} className={`flex items-start gap-3.5 px-3 py-2.5 rounded-2xl ${state === 'run' ? 'bg-amber-500/[0.08]' : ''}`}>
                  {state === 'done' ? (
                    <span className="w-7 h-7 rounded-full bg-emerald-500/15 text-emerald-300 flex items-center justify-center shrink-0"><Check className="w-4 h-4" /></span>
                  ) : state === 'run' ? (
                    <Loader2 className="w-7 h-7 p-1 text-amber-400 animate-spin shrink-0" />
                  ) : (
                    <span className="w-7 h-7 rounded-full border-2 border-neutral-700 shrink-0" />
                  )}
                  <span className="min-w-0 pt-0.5">
                    <span className={`block text-base ${state === 'run' ? 'font-semibold text-amber-200' : state === 'done' ? 'text-neutral-200' : 'text-neutral-500'}`}>{label}</span>
                    {state !== 'todo' && notes[key] && <span className="block text-[13px] text-neutral-400 break-words">{notes[key]}</span>}
                  </span>
                </li>
              );
            })}
          </ol>
          <p className="text-sm text-neutral-400">
            Usually 4–8 minutes. It cleans your footage, directs the story, designs every graphic and the music, then reviews its own work. You can leave this page.
          </p>
        </div>
      </section>

      <section aria-labelledby="premium-clips" className="flex-[999_1_420px] min-w-0 space-y-4">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <h2 id="premium-clips" className="font-syne text-2xl font-bold text-white">What it's editing</h2>
          <span className="text-[15px] text-neutral-400">{formatSeconds(clips.reduce((sum, s) => sum + s.duration_s, 0))} of footage</span>
        </div>
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3.5">
          {clips.map((source) => (
            <li key={source.key} className="rounded-[20px] border border-neutral-800 bg-neutral-900/80 overflow-hidden">
              <div className="relative aspect-[9/16] bg-neutral-950">
                {source.kind === 'image' && source.url && <img src={source.url} alt="" className="absolute inset-0 w-full h-full object-cover" />}
                {source.kind === 'video' && source.url && (
                  <video src={source.url} muted playsInline preload="metadata" aria-hidden="true" className="absolute inset-0 w-full h-full object-cover" />
                )}
                {source.duration_s > 0 && (
                  <span className="absolute left-2 bottom-2 px-1.5 py-0.5 rounded-md bg-black/70 font-mono text-xs font-semibold text-white">{formatSeconds(source.duration_s)}</span>
                )}
              </div>
              <p className="px-3 py-2.5 text-[13px] font-semibold text-neutral-200 truncate">{source.name}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
