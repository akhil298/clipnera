/**
 * Billing types. The entitlements, credit pack and payment shapes already live in
 * `lib/api/credits.ts` (the shell's credits popover); they are re-exported here, not
 * forked. The rest mirror backend/subscription/schema.py (PlanPriceResponse,
 * PlanOfferResponse, PlansResponse, CreditLedgerResponse) and
 * backend/subscription/entitlements.py (UsageKey, the feature keys). Keep them in step.
 * Datetimes are naive UTC ISO strings; read them with `parseApiDate`.
 */
import type { CreditPack, PlanCapabilities } from '@/lib/api/credits';

export type { CreditPack, Entitlements, Payment, PaymentStatus, PlanCapabilities } from '@/lib/api/credits';

/** backend/payment/schema.py PlanTypeValue. */
export type BillingPeriod = 'monthly' | 'yearly';

/** The keys of `PlanCapabilities.features` (entitlements.py `PlanFeature`). */
export type PlanFeature =
  | 'remove_watermark'
  | 'pro_ai'
  | 'all_hook_transitions'
  | 'brand_kit_edit'
  | 'depth_captions'
  | 'batch_processing'
  | 'team_members'
  | 'social_scheduling'
  | 'custom_aspect_ratios'
  | 'creator_intro';

/** The keys of `daily_limits` and `usage_today` (entitlements.py `UsageKey`). */
export type UsageKey = 'exports' | 'audio_enhancements' | 'reel_renders' | 'ai_shots' | 'auto_edits' | 'intro_renders';

/** PlanPriceResponse. `amount` is in whole units of `currency`. */
export interface PlanPrice {
  plan_type: BillingPeriod;
  amount: number;
  currency: string;
  days: number;
}

/** PlanOfferResponse. */
export interface PlanOffer {
  slug: string;
  name: string;
  capabilities: PlanCapabilities;
  prices: PlanPrice[];
}

/** PlansResponse (`GET /subscription/plans`). */
export interface PlansResponse {
  plans: PlanOffer[];
  credit_packs: CreditPack[];
}

/** CreditLedgerResponse (`GET /subscription/ledger`), newest first. */
export interface CreditLedgerEntry {
  id: string;
  user_id: string;
  /** Positive adds credits, negative spends them. */
  amount: number;
  /** The whole balance after this entry, bought and bonus credits included. */
  balance_after: number;
  /** Server text for support; never shown (it carries ids). See `ledgerReason`. */
  reason: string;
  reference_id: string | null;
  reference_type: string | null;
  created_at: string;
}
