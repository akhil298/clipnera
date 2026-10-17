'use client';

import React from 'react';
import { Check, Film, Image as ImageIcon, Link2, Loader2, Mic } from 'lucide-react';
import type { EditResponse } from '@/lib/api';
import { analysisSteps, formatSeconds } from '@/lib/utils/footageReels';

const KIND_ICON = { video: Film, image: ImageIcon, voice: Mic, reference: Link2 } as const;

/** While the footage is read and the plan made: where it is, what it is working from. */
export function FootageReelPlanning({ edit }: { edit: EditResponse }) {
  const hasReference = Boolean(edit.reference_url) || edit.sources.some((s) => s.kind === 'reference');
  const steps = ['Uploading your files', ...analysisSteps(hasReference)];
  // Uploading is always finished by the time analysis reports progress.
  const active = Math.max(1, edit.progress ? steps.indexOf(edit.progress) : 1);
  const clips = edit.sources.filter((s) => s.kind !== 'reference');
  const reference = edit.sources.find((s) => s.kind === 'reference');

  return (
    <div className="flex flex-wrap gap-6 items-start">
      <section aria-label="Progress" className="flex-[1_1_360px] min-w-0 space-y-4">
        <div className="rounded-[28px] border border-neutral-800 bg-neutral-900/80 p-6 sm:p-7 space-y-6">
          <div className="space-y-1.5">
            <p className="font-mono text-[13px] font-semibold text-amber-300">STEP {Math.min(active + 1, steps.length)} OF {steps.length}</p>
            <h2 className="font-syne text-3xl font-extrabold leading-tight text-white" aria-live="polite">{steps[active] ?? 'Getting started'}</h2>
          </div>
          <div className="h-2 rounded-full bg-neutral-800 overflow-hidden" aria-hidden="true">
            <div className="h-full rounded-full bg-amber-500 transition-[width] duration-700" style={{ width: `${((active + 0.5) / steps.length) * 100}%` }} />
          </div>
          <ol className="space-y-1">
            {steps.map((step, i) => {
              const state = i < active ? 'done' : i === active ? 'run' : 'todo';
              return (
                <li key={step} className={`flex items-center gap-3.5 px-3 py-2.5 rounded-2xl text-base ${state === 'run' ? 'bg-amber-500/[0.08] font-semibold text-amber-200' : state === 'done' ? 'text-neutral-200' : 'text-neutral-500'}`}>
                  {state === 'done' ? (
                    <span className="w-7 h-7 rounded-full bg-emerald-500/15 text-emerald-300 flex items-center justify-center shrink-0"><Check className="w-4 h-4" /></span>
                  ) : state === 'run' ? (
                    <Loader2 className="w-7 h-7 p-1 text-amber-400 animate-spin shrink-0" />
                  ) : (
                    <span className="w-7 h-7 rounded-full border-2 border-neutral-700 shrink-0" />
                  )}
                  {step}
                </li>
              );
            })}
          </ol>
          <p className="text-sm text-neutral-400">Usually 2–3 minutes. You can leave this page; we'll notify you when the plan is ready.</p>
        </div>

        <div className="rounded-3xl border border-neutral-800 bg-neutral-900/80 p-5 sm:p-6 space-y-3">
          <p className="text-[13px] font-semibold text-neutral-400">Your brief</p>
          <p className="text-base text-white">{edit.intent || 'No brief: the AI decides from your footage.'}</p>
          <div className="flex flex-wrap gap-2">
            <span className="h-8 inline-flex items-center px-3 rounded-full bg-neutral-800 text-[13px] font-semibold text-neutral-200">
              {edit.target_seconds ? `${edit.target_seconds} s` : 'Auto length'}
            </span>
            {edit.script && <span className="h-8 inline-flex items-center px-3 rounded-full bg-neutral-800 text-[13px] font-semibold text-neutral-200">Script added</span>}
            {hasReference && (
              <span className="h-8 inline-flex items-center gap-1.5 px-3 rounded-full bg-neutral-800 text-[13px] font-semibold text-neutral-200 max-w-full">
                <Link2 className="w-3.5 h-3.5 shrink-0" /> <span className="truncate">Like {reference?.name ?? edit.reference_url}</span>
              </span>
            )}
            <span className="h-8 inline-flex items-center px-3 rounded-full bg-amber-500/10 text-[13px] font-semibold text-amber-300">
              {edit.ai_model ? `${edit.ai_model} · ${edit.ai_effort ?? 'auto'} effort` : 'Auto model'}
            </span>
          </div>
        </div>
      </section>

      <section aria-labelledby="planning-clips" className="flex-[999_1_480px] min-w-0 space-y-4">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <h2 id="planning-clips" className="font-syne text-2xl font-bold text-white">What it's working from</h2>
          <span className="text-[15px] text-neutral-400">{formatSeconds(clips.reduce((sum, s) => sum + s.duration_s, 0))} of footage</span>
        </div>
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3.5">
          {clips.map((source) => {
            const Icon = KIND_ICON[source.kind];
            return (
              <li key={source.key} className="rounded-[20px] border border-neutral-800 bg-neutral-900/80 overflow-hidden">
                <div className="relative aspect-[9/16] bg-neutral-950 flex items-center justify-center">
                  {source.kind === 'image' && source.url ? <img src={source.url} alt="" className="absolute inset-0 w-full h-full object-cover" />
                    : source.kind === 'video' && source.url ? <video src={source.url} muted playsInline preload="metadata" aria-hidden="true" className="absolute inset-0 w-full h-full object-cover" />
                      : <Icon className="w-7 h-7 text-neutral-600" />}
                  <span className="absolute inset-0 bg-neutral-950/30 animate-pulse" aria-hidden="true" />
                  {source.duration_s > 0 && (
                    <span className="absolute left-2 bottom-2 px-1.5 py-0.5 rounded-md bg-black/70 font-mono text-xs font-semibold text-white">{formatSeconds(source.duration_s)}</span>
                  )}
                </div>
                <p className="px-3 py-2.5 text-[13px] font-semibold text-neutral-200 truncate">{source.name}</p>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
