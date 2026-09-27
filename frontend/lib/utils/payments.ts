import type { BillingPeriod, PaymentResponse } from '@/lib/api';
import { parseApiDate } from './dates';

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });

export function formatAmount(amount: number, currency: string): string {
  if (currency === 'INR') return inr.format(amount);
  return `${currency} ${amount}`;
}

export const BILLING_PERIOD_LABELS: Record<BillingPeriod, string> = { monthly: 'Monthly', yearly: 'Yearly' };

/** What a payment bought, e.g. "Pro Monthly" or "200 credits". */
export function paymentLabel(p: Pick<PaymentResponse, 'plan_name' | 'plan_type' | 'credits'>): string {
  if (p.credits) return `${p.credits} credits`;
  return `${p.plan_name ?? 'Plan'}${p.plan_type ? ` ${BILLING_PERIOD_LABELS[p.plan_type]}` : ''}`;
}

export function formatDateTime(iso: string): string {
  return parseApiDate(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/** UPI UTRs are 12 digits; apps often display them with spaces. */
export function normalizeUtr(raw: string): string {
  return raw.replace(/\s+/g, '');
}

export const UTR_PATTERN = /^\d{12}$/;
export const MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024;
export const SCREENSHOT_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
