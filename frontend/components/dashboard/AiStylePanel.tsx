'use client';

import { useEffect, useState } from 'react';
import { Sparkles, Trash2 } from 'lucide-react';
import { styleApi, type StylePreference } from '@/lib/api';

/** Settings → what the AI editor learned from your corrections, each one deletable. */
export function AiStylePanel() {
  const [prefs, setPrefs] = useState<StylePreference[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    styleApi.list().then(setPrefs).catch((err) => setError(err instanceof Error ? err.message : 'Could not load'));
  }, []);

  const forget = async (key: string) => {
    setError(null);
    try {
      setPrefs(await styleApi.forget(key));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete that');
    }
  };

  return (
    <section className="p-4 sm:p-6 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-3" aria-labelledby="ai-style-title">
      <h2 id="ai-style-title" className="text-sm font-bold text-white flex items-center gap-1.5">
        <Sparkles className="w-4 h-4 text-amber-400" aria-hidden />
        AI editor preferences
      </h2>
      <p className="text-[11.5px] text-neutral-500">
        Learned from how you correct the AI in the editor. What you ask for in a prompt always wins.
      </p>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {prefs === null ? (
        <p className="text-xs text-neutral-500">Loading…</p>
      ) : prefs.length === 0 ? (
        <p className="text-xs text-neutral-400">Nothing learned yet.</p>
      ) : (
        <ul className="divide-y divide-neutral-800">
          {prefs.map((p) => (
            <li key={p.key} className="flex items-center justify-between gap-3 py-2">
              <div className="min-w-0">
                <p className="text-sm text-white">{p.label}: <span className="text-neutral-300">{p.value}</span></p>
                <p className="text-[11px] text-neutral-500">
                  {Math.round(p.confidence * 100)}% sure{p.in_use ? ' · used in plans' : ' · not used yet'}
                </p>
              </div>
              <button type="button" onClick={() => void forget(p.key)} aria-label={`Forget ${p.label}`}
                className="p-1.5 rounded-lg text-neutral-500 hover:text-rose-400 hover:bg-neutral-800">
                <Trash2 className="w-4 h-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
