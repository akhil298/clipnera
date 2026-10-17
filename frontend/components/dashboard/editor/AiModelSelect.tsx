'use client';

import React from 'react';
import { Cpu, Gauge } from 'lucide-react';
import type { AiEffort } from '@/lib/api';
import { EFFORT_LABEL, useAiModels, useAiPick } from '@/lib/editor/aiPick';

const SELECT = 'h-9 appearance-none rounded-full border border-neutral-800 bg-transparent pl-8 pr-3 text-xs font-bold text-neutral-300 hover:border-neutral-600 hover:text-white focus:border-amber-400/60 focus:outline-none';

/** The model and reasoning effort the AI edits with, for the Editor home's start box. */
export function AiModelSelect() {
  const { model, effort, setModel, setEffort } = useAiPick();
  const choices = useAiModels();
  if (!choices) return null;

  return (
    <>
      <label className="relative" title="The model the AI edits with">
        <span className="sr-only">AI model</span>
        <Cpu className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-amber-400" aria-hidden />
        <select value={model ?? choices.default_model} onChange={(e) => setModel(e.target.value === choices.default_model ? null : e.target.value)} className={SELECT}>
          {choices.models.map((name) => (
            <option key={name} value={name} className="bg-neutral-900">
              {name}
            </option>
          ))}
        </select>
      </label>
      <label className="relative" title="How hard the AI thinks before it edits">
        <span className="sr-only">Reasoning effort</span>
        <Gauge className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-amber-400" aria-hidden />
        <select value={effort ?? ''} onChange={(e) => setEffort((e.target.value || null) as AiEffort | null)} className={SELECT}>
          <option value="" className="bg-neutral-900">
            Auto effort
          </option>
          {choices.efforts.map((name) => (
            <option key={name} value={name} className="bg-neutral-900">
              {EFFORT_LABEL[name]}
            </option>
          ))}
        </select>
      </label>
    </>
  );
}
