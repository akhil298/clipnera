'use client';

import React, { useState, useEffect } from 'react';
import { Check, CreditCard, Zap, Crown, Sparkles, Shield } from 'lucide-react';
import { subscriptionApi, PlanResponse } from '@/lib/api';

interface PlanSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPlanSelected: (plan: PlanResponse) => void;
  onActivateFree: () => void;
}

export function PlanSelectionModal({ isOpen, onClose, onPlanSelected, onActivateFree }: PlanSelectionModalProps) {
  const [plans, setPlans] = useState<PlanResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    async function loadPlans() {
      try {
        const data = await subscriptionApi.listPlans();
        if (!cancelled) {
          setPlans(data);
        }
      } catch (err) {
        if (!cancelled) setError('Failed to load plans');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadPlans();
    return () => { cancelled = true; };
  }, [isOpen]);

  const handleSelectPlan = (plan: PlanResponse) => {
    onPlanSelected(plan);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 lg:p-8">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl font-bold text-white font-['Syne',sans-serif]">Choose Your Plan</h2>
              <p className="text-sm text-neutral-400 mt-1">Select a plan that fits your content creation needs</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-neutral-800 border border-neutral-700 text-neutral-300 hover:text-white hover:border-neutral-600 transition-colors"
            >
              ✕
            </button>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
            </div>
          )}

          {error && (
            <div className="text-center py-20 text-red-400">{error}</div>
          )}

          {!loading && !error && (
            <div className="grid md:grid-cols-3 gap-6">
              {plans.map((plan) => {
                const isPro = plan.slug === 'pro';
                const isProPlus = plan.slug === 'pro_plus';
                return (
                  <div
                    key={plan.id}
                    className={`relative p-6 rounded-2xl flex flex-col justify-between ${
                      isPro
                        ? 'bg-gradient-to-b from-neutral-900 via-neutral-900 to-neutral-950 border-2 border-amber-500/60 shadow-xl shadow-amber-500/10'
                        : 'bg-neutral-950 border border-neutral-800'
                    }`}
                  >
                    {isPro && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-amber-500 text-[10px] font-extrabold text-neutral-950 uppercase tracking-wider">
                        Most Popular
                      </div>
                    )}
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        {plan.slug === 'free' && <Zap className="w-5 h-5 text-neutral-400" />}
                        {plan.slug === 'pro' && <Crown className="w-5 h-5 text-amber-400" />}
                        {plan.slug === 'pro_plus' && <Sparkles className="w-5 h-5 text-purple-400" />}
                        <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">{plan.name}</h3>
                      </div>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-extrabold text-white font-mono">
                          {plan.price_monthly === 0 ? 'Free' : `$${plan.price_monthly}`}
                        </span>
                        {plan.price_monthly > 0 && (
                          <span className="text-xs text-neutral-400">/month</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-neutral-300">
                        <Shield className="w-4 h-4 text-emerald-400" />
                        <span>{plan.credit_minutes} AI Processing Minutes / mo</span>
                      </div>
                      {plan.features && (
                        <ul className="space-y-2 text-xs text-neutral-300">
                          {plan.features.split(', ').map((feature) => (
                            <li key={feature} className="flex items-center gap-2">
                              <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                              <span>{feature}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <button
                      onClick={() => {
                        if (plan.slug === 'free') {
                          onActivateFree();
                        } else {
                          handleSelectPlan(plan);
                        }
                      }}
                      className={`w-full mt-6 py-3 rounded-xl text-sm font-bold transition-all active:scale-95 ${
                        isPro
                          ? 'bg-amber-500 hover:bg-amber-400 text-neutral-950 shadow-md shadow-amber-500/15'
                          : isProPlus
                          ? 'bg-purple-500 hover:bg-purple-400 text-white shadow-md shadow-purple-500/15'
                          : 'bg-neutral-800 hover:bg-neutral-700 text-white'
                      }`}
                    >
                      {plan.price_monthly === 0 ? 'Get Started Free' : `Choose ${plan.name}`}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
