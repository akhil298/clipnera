/**
 * The AI model and reasoning effort picked for the editor's prompts, shared by the Editor home's
 * start box and the studio's chat, and remembered by this browser.
 */

import { useEffect, useState } from 'react';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { type AiEffort, type AiModels, editorApi } from '@/lib/api';

export const EFFORT_LABEL: Record<AiEffort, string> = { low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high' };

interface AiPickState {
  /** null: the server's default model / each step's own effort. */
  model: string | null;
  effort: AiEffort | null;
  setModel: (model: string | null) => void;
  setEffort: (effort: AiEffort | null) => void;
}

export const useAiPick = create<AiPickState>()(
  persist(
    (set) => ({
      model: null,
      effort: null,
      setModel: (model) => set({ model }),
      setEffort: (effort) => set({ effort }),
    }),
    // Private windows may refuse storage; the pick then lasts for this visit.
    { name: 'clipnera-ai-pick', storage: createJSONStorage(() => localStorage) },
  ),
);

let offered: Promise<AiModels> | null = null;

/** What the server lets the user pick, fetched once per visit (again after a failure). */
export function loadAiModels(): Promise<AiModels> {
  offered ??= editorApi.models().catch((error: unknown) => {
    offered = null;
    throw error;
  });
  return offered;
}

/** The server's choices once loaded; a saved model it no longer offers goes back to the default. */
export function useAiModels(): AiModels | null {
  const [choices, setChoices] = useState<AiModels | null>(null);
  const model = useAiPick((state) => state.model);

  useEffect(() => {
    loadAiModels().then(setChoices, () => setChoices(null));
  }, []);

  useEffect(() => {
    if (choices && model && !choices.models.includes(model)) useAiPick.getState().setModel(null);
  }, [choices, model]);

  return choices;
}
