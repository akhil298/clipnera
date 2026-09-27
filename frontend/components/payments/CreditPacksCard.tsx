'use client';

import React, { useEffect, useState } from 'react';
import { Coins } from 'lucide-react';
import { subscriptionApi, type CreditPackResponse } from '@/lib/api';
import { useEntitlements, videoMinutesFor } from '@/hooks/useEntitlements';
import { formatAmount } from '@/lib/utils/payments';

/** Element id, so other screens can scroll straight to the packs. */
export const CREDIT_PACKS_ANCHOR = 'buy-credits';

/** One-off credit packs, bought through UPI on any plan. */
export function CreditPacksCard({ onSelect }: { onSelect: (pack: CreditPackResponse) => void }) {
  const { entitlements } = useEntitlements();
  const [packs, setPacks] = useState<CreditPackResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    subscriptionApi
      .getPlans()
      .then((data) => {
        if (!cancelled) setPacks(data.credit_packs);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || 'Could not load credit packs');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div id={CREDIT_PACKS_ANCHOR} className="p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl scroll-mt-24">
      <div>
        <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
          <Coins className="w-4 h-4 text-amber-400" />
          <span>Buy Credits</span>
        </h3>
        <p className="text-xs text-neutral-400 mt-1">
          One-off top-ups on any plan. Bought credits never expire and are used after your plan&apos;s monthly credits.
        </p>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {!error && packs === null && (
        <div className="grid sm:grid-cols-3 gap-3 animate-pulse">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-36 bg-neutral-800 rounded-xl" />
          ))}
        </div>
      )}

      {packs && (
        <div className="grid sm:grid-cols-3 gap-3">
          {packs.map((pack) => (
            <div key={pack.slug} className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 flex flex-col gap-3">
              <div>
                <p className="text-xs font-bold text-neutral-300">{pack.name}</p>
                <p className="text-2xl font-extrabold text-white font-mono">{pack.credits}</p>
                <p className="text-[11px] text-neutral-400">
                  credits · ≈ {videoMinutesFor(entitlements, pack.credits)} min of video
                </p>
              </div>
              <button
                onClick={() => onSelect(pack)}
                className="mt-auto w-full py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold active:scale-95 transition-all"
              >
                Buy for {formatAmount(pack.amount, pack.currency)}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
