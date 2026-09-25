'use client';

import { createContext, useContext } from 'react';
import type { EntitlementsResponse, PlanFeature } from '@/lib/api';
import { parseApiDate } from '@/lib/utils/dates';

/**
 * Capabilities of the signed-in user's plan.
 *
 * Every gated surface reads from here so the tier rules live in one place
 * (server-side, in subscription/entitlements.py) rather than being restated in
 * each component. The UI gate is for clarity, not security -- the same rules
 * are enforced on the API, so a bypassed control still fails server-side.
 */

/** Used until the real entitlements load, and if the request fails. Free-tier
 * shaped on purpose: showing a locked control briefly is recoverable, showing
 * a paid one to someone who cannot use it is not. */
export const FREE_TIER_FALLBACK: EntitlementsResponse = {
  plan: 'free',
  aspect_ratios: ['9:16'],
  caption_styles: ['clean_dark', 'default', 'hormozi', 'mrbeast', 'tiktok', 'bold_captions'],
  max_clips_per_video: 5,
  watermark_forced: true,
  pro_ai_provider: false,
  priority_rendering: false,
  max_upload_duration_seconds: 1800,
  credit_minutes: 60,
  all_hook_transitions: false,
  brand_kit_edit: false,
  depth_captions: false,
  batch_processing: false,
  team_members: false,
  daily_limits: { exports: 10, audio_enhancements: 3 },
  social_max_accounts: 1,
  social_platforms: ['youtube', 'tiktok', 'instagram'],
  social_scheduling: false,
  social_max_schedule_days: 0,
  social_posts_per_day: 3,
  features: {
    remove_watermark: false,
    pro_ai: false,
    all_hook_transitions: false,
    brand_kit_edit: false,
    depth_captions: false,
    batch_processing: false,
    team_members: false,
    social_scheduling: false,
  },
  credit_minutes_total: 0,
  credit_minutes_remaining: 0,
  current_period_end: null,
  subscription_status: 'none',
  plan_expires_at: null,
  next_credit_reset_at: null,
  usage_today: { exports: 0, audio_enhancements: 0 },
  has_pending_payment: false,
  show_plan_notice: false,
};

/** Whole days until a date (rounded up), or null when there is none or it has passed. */
export const daysUntil = (isoDate: string | null): number | null => {
  if (!isoDate) return null;
  const end = parseApiDate(isoDate).getTime();
  if (Number.isNaN(end)) return null;
  const days = Math.ceil((end - Date.now()) / 86_400_000);
  return days >= 0 ? days : null;
};

export interface EntitlementsContextValue {
  entitlements: EntitlementsResponse;
  isLoading: boolean;
  /** Opens the upgrade flow. Wired by the dashboard shell. */
  promptUpgrade: (reason?: string) => void;
  refresh: () => Promise<void>;
}

export const EntitlementsContext = createContext<EntitlementsContextValue>({
  entitlements: FREE_TIER_FALLBACK,
  isLoading: true,
  promptUpgrade: () => {},
  refresh: async () => {},
});

export const useEntitlements = (): EntitlementsContextValue =>
  useContext(EntitlementsContext);

/** Whether a caption style is usable on the current plan. */
export const canUseCaptionStyle = (
  entitlements: EntitlementsResponse,
  styleId: string,
): boolean =>
  entitlements.caption_styles === null || entitlements.caption_styles.includes(styleId);

/** Whether an output format is usable on the current plan. */
export const canUseAspectRatio = (
  entitlements: EntitlementsResponse,
  ratio: string,
): boolean => entitlements.aspect_ratios.includes(ratio);

/** Whether a plan slug is a paid tier. The one place the UI compares slugs. */
export const isPaidPlanSlug = (plan: string): boolean => plan !== 'free';

export const isPaidPlan = (entitlements: EntitlementsResponse): boolean => isPaidPlanSlug(entitlements.plan);

/** Whether the current plan includes a capability the API gates with PRO_REQUIRED. */
export const canUseFeature = (entitlements: EntitlementsResponse, feature: PlanFeature): boolean =>
  entitlements.features[feature];

/** Human-readable plan name for badges and labels. */
export const planLabel = (plan: string): string => {
  switch (plan) {
    case 'pro_plus':
      return 'Pro Plus';
    case 'pro':
      return 'Pro';
    case 'free':
      return 'Free';
    default:
      return plan.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
};
