'use client';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api/client';
import { parseApiDate } from '@/lib/utils/dates';
import { billingKeys } from '@/lib/query/keys/billing';

import type { Payment } from './types';

/**
 * `GET /payments/my` (list[PaymentResponse], bare body), newest first.
 * NEEDS-BACKEND: GET /payments/{id}/receipt (L-API-10). Until it exists there is no
 * receipt or invoice column (screens/03 L-D9).
 */
export const listPayments = (signal?: AbortSignal) => apiFetch<Payment[]>('/payments/my', { signal });

const PENDING_POLL_MS = 30_000;

const newestFirst = (a: Payment, b: Payment) => parseApiDate(b.created_at).getTime() - parseApiDate(a.created_at).getTime();

/**
 * Every payment the user submitted. Polls every 30 s only while one is being checked
 * (React Query pauses it in a hidden tab), until `entitlements.changed` lands (L-API-15).
 */
export function usePayments() {
  return useQuery({
    queryKey: billingKeys.payments(),
    queryFn: ({ signal }) => listPayments(signal),
    select: (payments) => [...payments].sort(newestFirst),
    staleTime: 60_000,
    refetchInterval: (query) => (query.state.data?.some((payment) => payment.status === 'pending') ? PENDING_POLL_MS : false),
  });
}

/** The one payment the page should call out, most urgent first (screens/03 §13 Alerts). */
export type PaymentAlert = { kind: 'declined'; payment: Payment } | { kind: 'pending'; payment: Payment };

/**
 * A declined payment wins when it is the newest one (nothing approved or pending since);
 * otherwise the newest payment still being checked. Credit-pack payments count too:
 * `has_pending_payment` only covers plan payments.
 */
export function paymentAlert(payments: readonly Payment[]): PaymentAlert | null {
  const [newest] = payments;
  if (newest && (newest.status === 'rejected' || newest.status === 'failed')) return { kind: 'declined', payment: newest };
  const pending = payments.find((payment) => payment.status === 'pending');
  return pending ? { kind: 'pending', payment: pending } : null;
}

/** Whether the user has ever had a paid plan approved (tells "Free" from "Pro ended"). */
export const hadPaidPlan = (payments: readonly Payment[]) => payments.some((payment) => payment.status === 'success' && payment.plan_slug !== null);
