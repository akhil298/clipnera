'use client';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api/client';
import { billingKeys } from '@/lib/query/keys/billing';

import type { CreditPack, PlanOffer, PlanPrice, PlansResponse } from './types';

/** `GET /subscription/plans` (PlansResponse, bare body). Public catalogue; same for everyone. */
export const getPlans = (signal?: AbortSignal) => apiFetch<PlansResponse>('/subscription/plans', { signal, auth: 'optional' });

/** Plans and credit packs. The catalogue only changes on deploy (frontend.md §3.4: Infinity). */
export function usePlans() {
  return useQuery({ queryKey: billingKeys.plans(), queryFn: ({ signal }) => getPlans(signal), staleTime: Infinity, gcTime: Infinity });
}

export const priceFor = (plan: PlanOffer, period: PlanPrice['plan_type']) => plan.prices.find((price) => price.plan_type === period);

/** Months a yearly price saves against twelve monthly ones ("Yearly · 2 months free"); 0 when none. */
export function monthsFree(plan: PlanOffer): number {
  const monthly = priceFor(plan, 'monthly');
  const yearly = priceFor(plan, 'yearly');
  if (!monthly || !yearly || monthly.amount <= 0) return 0;
  return Math.max(0, Math.round(12 - yearly.amount / monthly.amount));
}

/** Price of one credit in a pack, to two decimals ("₹1.65 a credit"). */
export const pricePerCredit = (pack: CreditPack) => (pack.credits > 0 ? pack.amount / pack.credits : 0);

/**
 * Where plan and pack purchases start. U6 builds the URL dialogs at
 * `/dashboard/plans?reason=` and `/dashboard/payment?plan=|pack=`; until they ship,
 * these point at the classic billing tab, which has the same plan and payment flow.
 * U6: return `/dashboard/plans${reason ? `?reason=${reason}` : ''}` and
 * `/dashboard/payment?pack=${slug}` / `?plan=${slug}&period=monthly`.
 */
const LEGACY_BILLING_HREF = `/api/ui/override?mode=classic&next=${encodeURIComponent('/dashboard/settings?tab=billing')}`;

export const plansHref = (_reason?: string) => LEGACY_BILLING_HREF;
export const packCheckoutHref = (_slug: string) => LEGACY_BILLING_HREF;
export const planCheckoutHref = (_slug: string) => LEGACY_BILLING_HREF;
