'use client';

import React, { useEffect, useState } from 'react';
import { Check, Clock, Crown, Lock, X, Zap } from 'lucide-react';
import {
  subscriptionApi,
  type BillingPeriod,
  type PlanOfferResponse,
} from '@/lib/api';
import { isPaidPlan, useEntitlements } from '@/hooks/useEntitlements';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { BILLING_PERIOD_LABELS, comparisonRows, formatAmount } from '@/lib/utils/payments';
import { ModalSkeleton } from '@/components/skeletons';

/** The plan and billing period a user chose to pay for. */
export interface SelectedPlan {
  slug: string;
  name: string;
  planType: BillingPeriod;
  creditMinutes: number;
}

interface PlanSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPlanSelected: (plan: SelectedPlan) => void;
  /** What the user tried to do that needs Pro, e.g. "The 16:9 format". */
  upgradeReason?: string;
}

const PERIOD_SUFFIX: Record<BillingPeriod, string> = { monthly: '/month', yearly: '/year' };

export function PlanSelectionModal({ isOpen, onClose, onPlanSelected, upgradeReason }: PlanSelectionModalProps) {
  const { entitlements } = useEntitlements();
  const { flags } = useFeatureFlags();
  const [plans, setPlans] = useState<PlanOfferResponse[]>([]);
  const [period, setPeriod] = useState<BillingPeriod>('monthly');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    subscriptionApi
      .getPlans()
      .then((data) => {
        if (!cancelled) setPlans(data.plans);
      })
      .catch(() => {
        if (!cancelled) setError('Failed to load plans');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const pending = entitlements.has_pending_payment;
  const monthly = plans.flatMap((p) => p.prices).find((price) => price.plan_type === 'monthly');
  const yearly = plans.flatMap((p) => p.prices).find((price) => price.plan_type === 'yearly');
  const yearlySavingMonths =
    monthly && yearly ? Math.round((monthly.amount * 12 - yearly.amount) / monthly.amount) : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 lg:p-8">
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              <h2 className="text-2xl font-bold text-white">Choose Your Plan</h2>
              <p className="text-sm text-neutral-400 mt-1">Start free. Upgrade when you need more.</p>
              {upgradeReason && (
                <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-amber-400/10 px-2.5 py-1 text-xs font-semibold text-amber-300 ring-1 ring-amber-400/25">
                  <Lock className="h-3.5 w-3.5" />
                  {upgradeReason} — available on Pro
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-neutral-800 border border-neutral-700 text-neutral-300 hover:text-white hover:border-neutral-600 transition-colors"
            >
              ✕
            </button>
          </div>

          {pending && (
            <div className="mb-6 flex items-center gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
              <Clock className="w-4 h-4 shrink-0" />
              Pro activation pending verification. We&apos;ll switch your plan as soon as your payment is approved.
            </div>
          )}

          {loading && <ModalSkeleton />}
          {error && <div className="text-center py-20 text-red-400">{error}</div>}

          {!loading && !error && (
            <>
              <div className="flex justify-center mb-6">
                <div className="flex gap-1 p-1 rounded-xl bg-neutral-950 border border-neutral-800">
                  {(Object.keys(PERIOD_SUFFIX) as BillingPeriod[]).map((p) => (
                    <button
                      key={p}
                      onClick={() => setPeriod(p)}
                      className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                        period === p ? 'bg-amber-500 text-neutral-950' : 'text-neutral-300 hover:text-white'
                      }`}
                    >
                      {BILLING_PERIOD_LABELS[p]}
                      {p === 'yearly' && yearlySavingMonths > 0 && (
                        <span className={period === p ? 'ml-1 text-neutral-900' : 'ml-1 text-emerald-400'}>
                          · {yearlySavingMonths} months free
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {plans.map((plan) => {
                  const price = plan.prices.find((p) => p.plan_type === period);
                  const isCurrent = entitlements.plan === plan.slug;
                  const isPaid = Boolean(price);
                  return (
                    <div
                      key={plan.slug}
                      className={`relative p-6 rounded-2xl flex flex-col justify-between ${
                        isPaid
                          ? 'bg-gradient-to-b from-neutral-900 via-neutral-900 to-neutral-950 border-2 border-amber-500/60 shadow-xl shadow-amber-500/10'
                          : 'bg-neutral-950 border border-neutral-800'
                      }`}
                    >
                      <div className="space-y-4">
                        <div className="flex items-center gap-2">
                          {isPaid ? <Crown className="w-5 h-5 text-amber-400" /> : <Zap className="w-5 h-5 text-neutral-400" />}
                          <h3 className="text-base font-bold text-white">{plan.name}</h3>
                          {isCurrent && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-neutral-800 text-neutral-300 font-bold">
                              Current
                            </span>
                          )}
                        </div>
                        <div className="flex items-baseline gap-1">
                          <span className="text-3xl font-extrabold text-white tabular-nums">
                            {price ? formatAmount(price.amount, price.currency) : formatAmount(0, 'INR')}
                          </span>
                          {price && <span className="text-xs text-neutral-400">{PERIOD_SUFFIX[period]}</span>}
                        </div>
                        <ul className="space-y-2 text-xs">
                          {comparisonRows(plan.capabilities, flags.social_publishing).map((row) => (
                            <li
                              key={row.label}
                              className={`flex items-center gap-2 ${row.included ? 'text-neutral-300' : 'text-neutral-500'}`}
                            >
                              {row.included ? (
                                <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                              ) : (
                                <X className="w-4 h-4 flex-shrink-0" />
                              )}
                              <span>{row.label}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {isPaid ? (
                        <button
                          disabled={pending}
                          onClick={() =>
                            onPlanSelected({
                              slug: plan.slug,
                              name: plan.name,
                              planType: period,
                              creditMinutes: plan.capabilities.credit_minutes,
                            })
                          }
                          className="w-full mt-6 py-3 rounded-xl text-sm font-bold transition-all active:scale-95 bg-amber-500 hover:bg-amber-400 text-neutral-950 shadow-md shadow-amber-500/15 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
                        >
                          {pending
                            ? 'Pending verification'
                            : isCurrent
                            ? `Renew ${plan.name}`
                            : `Upgrade to ${plan.name}`}
                        </button>
                      ) : (
                        <div className="w-full mt-6 py-3 rounded-xl text-sm font-bold text-center bg-neutral-800/60 text-neutral-400 ring-1 ring-neutral-700">
                          {isCurrent ? 'Current Plan' : 'Always free'}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {isPaidPlan(entitlements) && (
                <p className="mt-4 text-center text-[11px] text-neutral-500">
                  Renewing adds the new period on top of your current end date.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
