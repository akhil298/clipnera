import { apiFetch } from './client';

/**
 * Credit balance, plan and top-up options for the credits popover. Types mirror
 * backend/subscription/schema.py (EntitlementsResponse, PlanCapabilities,
 * CreditPackResponse) and backend/payment/schema.py (PaymentResponse); keep them in step.
 * These routes return the model directly; apiFetch passes a bare body through.
 */

/** PlanCapabilities. */
export interface PlanCapabilities {
  plan: string;
  aspect_ratios: string[];
  /** null means every style. */
  caption_styles: string[] | null;
  max_clips_per_video: number;
  watermark_forced: boolean;
  pro_ai_provider: boolean;
  priority_rendering: boolean;
  max_upload_duration_seconds: number;
  credit_minutes: number;
  all_hook_transitions: boolean;
  brand_kit_edit: boolean;
  depth_captions: boolean;
  batch_processing: boolean;
  team_members: boolean;
  /** Per UTC day; null means unlimited. */
  daily_limits: Record<string, number | null>;
  social_max_accounts: number;
  social_platforms: string[];
  social_scheduling: boolean;
  social_max_schedule_days: number;
  social_posts_per_day: number;
  custom_aspect_ratios: boolean;
  creator_intro: boolean;
  features: Record<string, boolean>;
}

/** EntitlementsResponse (`GET /subscription/entitlements`). Datetimes are naive UTC ISO strings. */
export interface Entitlements extends PlanCapabilities {
  credit_minutes_total: number;
  /** Everything spendable now: plan credits plus bought ones. */
  credit_minutes_remaining: number;
  /** The bought part of `credit_minutes_remaining`; never expires. */
  purchased_credits_remaining: number;
  current_period_end: string | null;
  subscription_status: string;
  plan_expires_at: string | null;
  next_credit_reset_at: string | null;
  usage_today: Record<string, number>;
  credits_per_video_minute: number;
  extra_aspect_ratio_credit_share: number;
  has_pending_payment: boolean;
  show_plan_notice: boolean;
}

/** CreditPackResponse. `amount` is in whole units of `currency`. */
export interface CreditPack {
  slug: string;
  name: string;
  credits: number;
  amount: number;
  currency: string;
}

/** backend/payment/schema.py PaymentStatusValue. */
export type PaymentStatus = 'pending' | 'success' | 'failed' | 'rejected';

/** PaymentResponse (`GET /payments/my`): a plan payment sets plan_*, a credit-pack one sets credit_pack and credits. */
export interface Payment {
  id: string;
  plan_slug: string | null;
  plan_name: string | null;
  plan_type: 'monthly' | 'yearly' | null;
  credit_pack: string | null;
  credits: number | null;
  amount: number;
  currency: string;
  utr_number: string | null;
  status: PaymentStatus;
  rejection_reason: string | null;
  screenshot_url: string | null;
  verified_at: string | null;
  created_at: string;
}

export const getEntitlements = (signal?: AbortSignal) => apiFetch<Entitlements>('/subscription/entitlements', { signal });

/** Credit packs on sale, from PlansResponse.credit_packs (the plans themselves belong to the billing page). */
export async function listCreditPacks(signal?: AbortSignal): Promise<CreditPack[]> {
  const { credit_packs: packs } = await apiFetch<{ credit_packs: CreditPack[] }>('/subscription/plans', { signal });
  return packs;
}

/** The caller's newest payment still waiting for an admin, if any. */
export async function getPendingPayment(signal?: AbortSignal): Promise<Payment | null> {
  const payments = await apiFetch<Payment[]>('/payments/my', { signal });
  return payments.find((payment) => payment.status === 'pending') ?? null;
}
