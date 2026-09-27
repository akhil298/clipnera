'use client';

import { useEffect, useState } from 'react';
import { Check, X } from 'lucide-react';
import { subscriptionApi, type PlansResponse } from '@/lib/api';
import { comparisonRows, formatAmount } from '@/lib/utils/payments';

interface PricingSectionProps {
  onLaunchStudio: () => void;
}

const PERIOD_SUFFIX = { monthly: '/month', yearly: '/year' } as const;

/** Plans, prices and limits come from the server, the same rules the app enforces. */
export function PricingSection({ onLaunchStudio }: PricingSectionProps) {
  const [offers, setOffers] = useState<PlansResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    subscriptionApi.getPublicPlans().then(setOffers).catch(() => setFailed(true));
  }, []);

  return (
    <section id="pricing" className="py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">
            Transparent Pricing
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white font-['Syne',sans-serif]">
            Simple plans for creators of all sizes
          </h2>
          <p className="text-xs text-neutral-300">
            Start free. Prices in Indian rupees; the amount shown is the amount you pay. Pro does not renew automatically.
          </p>
        </div>

        {failed && (
          <p className="text-center text-xs text-neutral-300">
            Pricing could not be loaded. Sign in to see plans and prices.
          </p>
        )}

        {!offers && !failed && (
          <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto" aria-busy="true" aria-label="Loading plans">
            {[0, 1].map((i) => (
              <div key={i} className="h-96 rounded-2xl bg-neutral-900/90 border border-neutral-800 animate-pulse" />
            ))}
          </div>
        )}

        {offers && (
          <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
            {offers.plans
              .filter((plan) => plan.slug === 'free' || plan.prices.length > 0)
              .map((plan) => {
              const paid = plan.prices.length > 0;
              return (
                <div
                  key={plan.slug}
                  className={`p-6 rounded-2xl space-y-6 flex flex-col justify-between ${
                    paid
                      ? 'bg-gradient-to-b from-neutral-900 via-neutral-900 to-neutral-950 border-2 border-amber-500/60 shadow-xl shadow-amber-500/10'
                      : 'bg-neutral-900/90 border border-neutral-800'
                  }`}
                >
                  <div className="space-y-4">
                    <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">{plan.name}</h3>
                    <div className="space-y-1">
                      {paid ? (
                        plan.prices.map((price) => (
                          <p key={price.plan_type} className="flex items-baseline gap-1">
                            <span className="text-3xl font-extrabold text-white font-mono">
                              {formatAmount(price.amount, price.currency)}
                            </span>
                            <span className="text-xs text-neutral-300">{PERIOD_SUFFIX[price.plan_type]}</span>
                          </p>
                        ))
                      ) : (
                        <p className="text-3xl font-extrabold text-white font-mono">{formatAmount(0, 'INR')}</p>
                      )}
                    </div>
                    <ul className="space-y-2.5 text-xs text-neutral-300">
                      {comparisonRows(plan.capabilities, false).map((row) => (
                        <li key={row.label} className={`flex items-center gap-2 ${row.included ? '' : 'text-neutral-400'}`}>
                          {row.included ? (
                            <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" aria-hidden="true" />
                          ) : (
                            <X className="w-4 h-4 text-neutral-500 flex-shrink-0" aria-hidden="true" />
                          )}
                          <span>
                            <span className="sr-only">{row.included ? 'Included: ' : 'Not included: '}</span>
                            {row.label}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <button
                    onClick={onLaunchStudio}
                    className={`w-full py-2.5 rounded-xl text-xs font-bold transition-all active:scale-95 ${
                      paid
                        ? 'bg-amber-500 hover:bg-amber-400 text-neutral-950 shadow-md shadow-amber-500/15'
                        : 'bg-neutral-800 hover:bg-neutral-700 text-white'
                    }`}
                  >
                    {paid ? `Get ${plan.name}` : 'Get Started Free'}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {offers && offers.credit_packs.length > 0 && (
          <p className="text-center text-xs text-neutral-300">
            Need more? One-time credit packs that never expire:{' '}
            {offers.credit_packs
              .map((pack) => `${pack.credits} credits for ${formatAmount(pack.amount, pack.currency)}`)
              .join(' · ')}
            . See our <a href="/refunds" className="text-amber-300 underline underline-offset-2">Refund Policy</a>.
          </p>
        )}
      </div>
    </section>
  );
}
