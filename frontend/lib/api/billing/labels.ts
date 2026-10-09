import type { Status } from '@/components/ui';

import type { BillingPeriod, CreditLedgerEntry, Payment, PaymentStatus, PlanFeature, UsageKey } from './types';

/**
 * Words for billing: feature names for plan locks, usage meters, payment and ledger
 * rows. Pure, so any screen (and U6's dialogs) can use them. Legacy keeps its own
 * copies in hooks/usePlan.ts and lib/utils/payments.ts.
 */

/** What each gated capability is called in a lock or the plans dialog's reason badge. */
export const FEATURE_LABELS: Record<PlanFeature, string> = {
  remove_watermark: 'Removing the watermark',
  pro_ai: 'The Pro AI models',
  all_hook_transitions: 'Hook transition presets',
  brand_kit_edit: 'Creating and editing brand kits',
  depth_captions: 'Depth captions',
  batch_processing: 'Batch processing',
  team_members: 'Adding team members',
  social_scheduling: 'Scheduling social posts',
  custom_aspect_ratios: 'Choosing output formats',
  creator_intro: 'Your channel intro',
};

export const isPlanFeature = (key: string): key is PlanFeature => key in FEATURE_LABELS;

/** Usage meters, in the order the billing page shows them (screens/03 §13). */
export const USAGE_LABELS: Record<UsageKey, string> = {
  exports: 'Exports',
  audio_enhancements: 'Audio clean-ups',
  reel_renders: 'Reel renders',
  ai_shots: 'AI shots',
  auto_edits: 'Footage edits',
  intro_renders: 'Channel intro renders',
};

export const USAGE_ORDER = Object.keys(USAGE_LABELS) as UsageKey[];

const PERIOD_LABELS: Record<BillingPeriod, string> = { monthly: 'Monthly', yearly: 'Yearly' };

export const formatCredits = (value: number) => value.toLocaleString('en-IN');

/** "₹699". Amounts are whole units of the currency. */
export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
}

/** What a payment bought: "Pro · Monthly" or "200 credits". */
export function paymentLabel(payment: Pick<Payment, 'plan_name' | 'plan_type' | 'credits'>): string {
  if (payment.credits) return `${formatCredits(payment.credits)} credits`;
  const name = payment.plan_name ?? 'Plan';
  return payment.plan_type ? `${name} · ${PERIOD_LABELS[payment.plan_type]}` : name;
}

/** How a payment's status reads in a `StatusBadge`. */
export const PAYMENT_STATUS: Record<PaymentStatus, { status: Status; label: string }> = {
  pending: { status: 'processing', label: 'Checking' },
  success: { status: 'ready', label: 'Approved' },
  rejected: { status: 'failed', label: 'Rejected' },
  failed: { status: 'failed', label: 'Failed' },
};

/** Ledger `reference_type` values written by the backend → plain words. */
const LEDGER_REASONS: Record<string, string> = {
  credit_refill: 'Plan credits renewed',
  credit_pack: 'Credit pack bought',
  bonus_grant: 'Bonus credits added',
  bonus_expired: 'Bonus credits expired',
  bonus_voided: 'Bonus credits taken back',
  admin_topup: 'Added by Clipnera support',
  video_project: 'Clips from a video',
  video_project_resume: 'Clips from a video (resumed)',
  video_project_refund: 'Refund: making clips didn’t finish',
  reel_render: 'Reel render',
  reel_render_refund: 'Refund: reel render didn’t finish',
  edit_render: 'Footage reel',
  edit_render_refund: 'Refund: footage reel didn’t finish',
  ai_scene: 'AI shot',
  ai_scene_refund: 'Refund: AI shot didn’t finish',
  broll_clip: 'B-roll cutaways',
};

/**
 * A ledger row's reason in plain words. The server's `reason` text carries ids, so it
 * is never shown. NEEDS-BACKEND: the project title for "Clips from 'Episode 41'"
 * (the row only has `reference_id`).
 */
export function ledgerReason(entry: Pick<CreditLedgerEntry, 'amount' | 'reference_type'>): string {
  const known = entry.reference_type ? LEDGER_REASONS[entry.reference_type] : undefined;
  return known ?? (entry.amount >= 0 ? 'Credits added' : 'Credits used');
}
