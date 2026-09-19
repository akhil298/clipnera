'use client';

import { createContext, useContext } from 'react';
import type { EntitlementsResponse } from '@/lib/api';

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
  caption_styles: ['default', 'hormozi', 'mrbeast', 'tiktok', 'bold_captions'],
  max_clips_per_video: 5,
  watermark_forced: true,
  pro_ai_provider: false,
  priority_rendering: false,
  max_upload_duration_seconds: 1800,
  credit_minutes_total: 0,
  credit_minutes_remaining: 0,
  current_period_end: null,
  subscription_status: 'none',
};

/** Days until the credit quota resets, or null when there is no active period. */
export const daysUntilRenewal = (isoDate: string | null): number | null => {
  if (!isoDate) return null;
  const end = new Date(isoDate).getTime();
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

export const isPaidPlan = (entitlements: EntitlementsResponse): boolean =>
  entitlements.plan !== 'free';

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
