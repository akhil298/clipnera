'use client';

import React, { useEffect, useState } from 'react';
import { adminAiEditorApi, type RolloutMetrics } from '@/lib/api';

/** The AI editor rollout at a glance: turns, cost per turn and undo rate over the last week. */
export function AiEditorMetrics({ onError }: { onError: (message: string) => void }) {
  const [metrics, setMetrics] = useState<RolloutMetrics | null>(null);

  useEffect(() => {
    adminAiEditorApi.metrics(7).then(setMetrics).catch((err: Error) => onError(err.message));
  }, [onError]);

  if (!metrics) return <p className="text-xs text-neutral-400">Loading…</p>;
  const cells = [
    ['Turns', String(metrics.turns)],
    ['Plans approved', `${metrics.plans_approved} of ${metrics.plans}`],
    ['Cost per turn', `$${metrics.cost_per_turn_usd.toFixed(4)}`],
    ['Undo rate', `${Math.round(metrics.undo_rate * 100)}% of ${metrics.ai_steps} AI steps`],
  ];
  return (
    <div className="space-y-2">
      <p className="text-xs font-bold text-white">AI editor — last {metrics.days} days</p>
      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {cells.map(([label, value]) => (
          <div key={label} className="rounded-xl bg-neutral-950 border border-neutral-800 p-2.5">
            <dt className="text-[11px] text-neutral-500">{label}</dt>
            <dd className="text-sm font-semibold text-white">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
