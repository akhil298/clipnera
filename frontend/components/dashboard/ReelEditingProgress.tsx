'use client';

import React from 'react';
import { Check, Download, Sparkles } from 'lucide-react';
import type { EditResponse } from '@/lib/api';
import { editPhase } from '@/lib/utils/footageReels';

/** While a reel is being made: the footage, softly, and a few plain steps. The engine's own stages stay out of sight. */
export function ReelEditingProgress({ edit }: { edit: EditResponse }) {
  const { steps, active, minutesLeft } = editPhase(edit);
  const cover = edit.sources.find((s) => s.kind === 'video' && s.url) ?? edit.sources.find((s) => s.kind === 'image' && s.url);
  const percent = ((active + 0.5) / steps.length) * 100;
  // After the moments are found: how many reels this video gives, and how many are done.
  const found = edit.premium?.stages.find((s) => s.stage === 'moments');
  const many = Number((found?.note ?? '').match(/^(\d+)/)?.[1] ?? 1);

  return (
    <div className="mx-auto max-w-5xl flex flex-wrap items-center justify-center gap-10 lg:gap-16 py-2">
      <div className="relative w-[260px] sm:w-[300px] aspect-[9/16] rounded-[28px] overflow-hidden bg-neutral-900 border border-neutral-800 shadow-2xl shadow-amber-500/10 shrink-0" aria-hidden="true">
        {cover?.kind === 'video' && cover.url && (
          <video src={cover.url} autoPlay muted loop playsInline className="absolute inset-0 w-full h-full object-cover scale-110 blur-[3px] opacity-60" />
        )}
        {cover?.kind === 'image' && cover.url && <img src={cover.url} alt="" className="absolute inset-0 w-full h-full object-cover scale-110 blur-[3px] opacity-60" />}
        <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/10 to-black/70" />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="relative flex w-16 h-16">
            <span className="absolute inset-0 rounded-full bg-amber-400/30 animate-ping" />
            <span className="relative w-16 h-16 rounded-full bg-amber-500 text-neutral-950 flex items-center justify-center shadow-lg shadow-amber-500/30">
              <Sparkles className="w-7 h-7" />
            </span>
          </span>
        </div>
        <div className="absolute left-5 right-5 bottom-6 space-y-2">
          <div className="h-3.5 w-3/4 rounded-md bg-white/15 animate-pulse" />
          <div className="h-3.5 w-1/2 rounded-md bg-amber-400/60 animate-pulse" />
        </div>
      </div>

      <section aria-label="Progress" className="flex-[1_1_360px] max-w-md min-w-0 space-y-7">
        <div className="space-y-2">
          <p className="text-[13px] font-bold tracking-[0.14em] text-amber-300">EDITING</p>
          <h2 className="font-syne text-4xl font-extrabold leading-[1.08] text-white" aria-live="polite">
            {many > 1 ? `We're making ${many} reels` : <>We&apos;re editing your reel</>}
          </h2>
          <p className="text-base text-neutral-400">
            {many > 1 ? `Your video has ${many} strong moments. ${edit.reels.length} of ${many} ready. ` : ''}
            {many > 1 ? 'You can close this tab; we\'ll let you know when they\'re ready.'
              : <>About {minutesLeft} minute{minutesLeft === 1 ? '' : 's'} left. You can close this tab; we&apos;ll let you know when it&apos;s ready.</>}
          </p>
        </div>

        <div className="h-2 rounded-full bg-neutral-800 overflow-hidden" role="progressbar" aria-label="Edit progress"
          aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)}>
          <div className="h-full rounded-full bg-amber-500 transition-[width] duration-700" style={{ width: `${percent}%` }} />
        </div>

        <ol className="space-y-1.5">
          {steps.map((step, i) => {
            const state = i < active ? 'done' : i === active ? 'run' : 'todo';
            return (
              <li key={step} className={`flex items-center gap-4 px-4 py-3 rounded-2xl border transition-colors ${
                state === 'run' ? 'border-neutral-700 bg-neutral-900' : 'border-transparent'
              }`}>
                {state === 'done' ? (
                  <span className="w-7 h-7 rounded-full bg-emerald-500/15 text-emerald-300 flex items-center justify-center shrink-0"><Check className="w-4 h-4" /></span>
                ) : state === 'run' ? (
                  <span className="w-7 h-7 rounded-full border-[3px] border-amber-500 flex items-center justify-center shrink-0">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
                  </span>
                ) : (
                  <span className="w-7 h-7 rounded-full border-2 border-neutral-700 shrink-0" />
                )}
                <span className={`text-base ${state === 'run' ? 'font-semibold text-white' : state === 'done' ? 'text-neutral-300' : 'text-neutral-500'}`}>{step}</span>
              </li>
            );
          })}
        </ol>

        {many > 1 && edit.reels.length > 0 && (
          <div className="space-y-3">
            <p className="text-[13px] font-bold tracking-[0.14em] text-emerald-300">READY NOW</p>
            <ul className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3">
              {edit.reels.map((reel, i) => (
                <li key={reel.url ?? i} className="relative rounded-2xl overflow-hidden border border-neutral-800 bg-black">
                  <video src={reel.url ?? undefined} controls playsInline preload="metadata" className="w-full aspect-[9/16]" />
                  {reel.url && (
                    <a href={reel.url} download aria-label={`Download reel ${i + 1}`}
                      className="absolute top-2 right-2 w-9 h-9 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 flex items-center justify-center">
                      <Download className="w-4 h-4" />
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
