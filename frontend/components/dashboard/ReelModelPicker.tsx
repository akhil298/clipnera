'use client';

import React from 'react';
import { Cpu, Gauge, Lock, Sparkles } from 'lucide-react';
import type { AiEffort } from '@/lib/api';
import { EFFORT_LABEL, loadReelModels, useAiModels, useAiPick } from '@/lib/editor/aiPick';
import { useEntitlements } from '@/hooks/useEntitlements';

const chip = (on: boolean) =>
  `h-11 px-4 rounded-full border text-sm font-semibold transition-colors disabled:opacity-40 inline-flex items-center gap-1.5 ${
    on ? 'border-amber-500 bg-amber-500 text-neutral-950' : 'border-neutral-800 bg-neutral-900 text-neutral-300 hover:text-white hover:border-neutral-700'
  }`;
const segment = (on: boolean) =>
  `h-9 px-3.5 rounded-[10px] text-[13px] font-semibold transition-colors disabled:opacity-40 ${
    on ? 'bg-neutral-700 text-white' : 'text-neutral-400 hover:text-white'
  }`;
const SELECT = 'h-9 appearance-none rounded-full border border-neutral-800 bg-neutral-900 pl-8 pr-3 text-xs font-semibold text-neutral-300 hover:text-white focus:border-amber-400/60 focus:outline-none';

/** The model and effort a reel request carries: none unless the plan allows picking (Pro), and effort only with a model. */
export function useReelPick(): { ai_model: string | null; ai_effort: AiEffort | null } {
  const { model, effort } = useAiPick();
  const { entitlements } = useEntitlements();
  if (!entitlements?.pro_ai_provider || !model) return { ai_model: null, ai_effort: null };
  return { ai_model: model, ai_effort: effort };
}

/** Big model chips and an effort switch, for starting a reel. */
export function ReelModelPicker({ disabled }: { disabled?: boolean }) {
  const { model, effort, setModel, setEffort } = useAiPick();
  const choices = useAiModels(loadReelModels);
  const { entitlements, promptUpgrade } = useEntitlements();
  const isPro = Boolean(entitlements?.pro_ai_provider);
  if (!choices) return null;
  const picked = isPro ? model : null;

  return (
    <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
      <div className="space-y-2 min-w-0">
        <span className="flex items-center gap-1.5 text-[13px] font-semibold text-neutral-400">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" aria-hidden /> AI model
          {!isPro && <span className="font-normal text-neutral-500">· picking one is on Pro</span>}
        </span>
        <div role="group" aria-label="AI model" className="flex flex-wrap gap-1.5">
          <button type="button" disabled={disabled} aria-pressed={picked === null} onClick={() => setModel(null)} className={chip(picked === null)}>
            Auto
          </button>
          {choices.models.map((name) => (
            <button key={name} type="button" disabled={disabled} aria-pressed={picked === name}
              onClick={() => (isPro ? setModel(name) : promptUpgrade('ai_model'))} className={chip(picked === name)}>
              {!isPro && <Lock className="w-3.5 h-3.5" aria-hidden />}
              {name}
            </button>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        <span className="block text-[13px] font-semibold text-neutral-400">How hard it thinks</span>
        <div role="group" aria-label="Reasoning effort" className="flex flex-wrap gap-0.5 p-1 rounded-[13px] bg-neutral-900 border border-neutral-800">
          {[null, ...choices.efforts].map((name) => (
            <button key={name ?? 'auto'} type="button" disabled={disabled || picked === null} aria-pressed={effort === name}
              title={picked === null ? 'Pick a model to set its effort' : undefined}
              onClick={() => setEffort(name)} className={segment(picked !== null && effort === name)}>
              {name ? EFFORT_LABEL[name] : 'Auto'}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/** The same pick as two small selects, for the reel's chat; hidden on plans that can't pick. */
export function ReelModelSelect({ disabled }: { disabled?: boolean }) {
  const { model, effort, setModel, setEffort } = useAiPick();
  const choices = useAiModels(loadReelModels);
  const { entitlements } = useEntitlements();
  if (!choices || !entitlements?.pro_ai_provider) return null;

  return (
    <>
      <label className="relative" title="The model the editor uses">
        <span className="sr-only">AI model</span>
        <Cpu className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-amber-400" aria-hidden />
        <select value={model ?? ''} disabled={disabled} onChange={(e) => setModel(e.target.value || null)} className={SELECT}>
          <option value="" className="bg-neutral-900">Auto model</option>
          {choices.models.map((name) => <option key={name} value={name} className="bg-neutral-900">{name}</option>)}
        </select>
      </label>
      {model && (
        <label className="relative" title="How hard the editor thinks">
          <span className="sr-only">Reasoning effort</span>
          <Gauge className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-amber-400" aria-hidden />
          <select value={effort ?? ''} disabled={disabled} onChange={(e) => setEffort((e.target.value || null) as AiEffort | null)} className={SELECT}>
            <option value="" className="bg-neutral-900">Auto effort</option>
            {choices.efforts.map((name) => <option key={name} value={name} className="bg-neutral-900">{EFFORT_LABEL[name]}</option>)}
          </select>
        </label>
      )}
    </>
  );
}
