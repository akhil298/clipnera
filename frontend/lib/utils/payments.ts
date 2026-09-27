import type { BillingPeriod, PaymentResponse, PlanCapabilities } from '@/lib/api';
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

const limitLabel = (limit: number | null, noun: string) =>
  limit === null ? `Unlimited ${noun}` : `${limit} ${noun} a day`;

/** The comparison rows for a plan, all derived from the server's plan rules. */
export function comparisonRows(c: PlanCapabilities, social: boolean): { label: string; included: boolean }[] {
  return [
    { label: `${c.credit_minutes} credits every 30 days`, included: true },
    { label: `Videos up to ${Math.round(c.max_upload_duration_seconds / 60)} min`, included: true },
    { label: `${c.max_clips_per_video} clips per video`, included: true },
    { label: `Formats: ${c.aspect_ratios.join(', ')}`, included: true },
    { label: 'Choose output formats per video', included: c.custom_aspect_ratios },
    {
      label: c.caption_styles === null ? 'Every caption style' : `${c.caption_styles.length} caption styles`,
      included: true,
    },
    { label: limitLabel(c.daily_limits.exports, 'exports'), included: true },
    { label: limitLabel(c.daily_limits.audio_enhancements, 'audio enhancements'), included: true },
    { label: 'No watermark', included: !c.watermark_forced },
    { label: 'Pro AI models', included: c.pro_ai_provider },
    { label: 'All hook transitions', included: c.all_hook_transitions },
    { label: 'Create and edit brand kits', included: c.brand_kit_edit },
    { label: 'Add team members', included: c.team_members },
    { label: 'Depth captions', included: c.depth_captions },
    { label: 'Batch processing', included: c.batch_processing },
    ...(social
      ? [
          { label: `${c.social_max_accounts} connected social account${c.social_max_accounts === 1 ? '' : 's'}`, included: true },
          { label: `${c.social_posts_per_day} social posts a day`, included: true },
          { label: 'Schedule social posts', included: c.social_scheduling },
          { label: 'Publish to X', included: c.social_platforms.includes('x') },
        ]
      : []),
  ];
}
