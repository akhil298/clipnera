'use client';

import { useMemo } from 'react';
import type { PlanFeature, UpgradeRequiredDetail, UsageKey } from '@/lib/api';
import { canUseFeature, daysUntil, isPaidPlan, useEntitlements } from './useEntitlements';

/** Days before expiry at which Pro users are asked to renew. */
export const RENEWAL_REMINDER_DAYS = 3;

/** What each gated capability is called in upgrade prompts. */
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

const USAGE_LABELS: Record<UsageKey, string> = {
  exports: 'export',
  audio_enhancements: 'audio enhancement',
  reel_renders: 'reel render',
  ai_shots: 'AI shot',
  auto_edits: 'footage edit',
  intro_renders: 'channel intro render',
};

/** The upgrade-prompt reason for a plan error returned by the API. */
export function upgradeReasonFor(detail: UpgradeRequiredDetail): string {
  if (detail.error === 'LIMIT_REACHED' && detail.feature && detail.feature in USAGE_LABELS) {
    return `Going past today's ${USAGE_LABELS[detail.feature as UsageKey]} limit`;
  }
  if (detail.error === 'INSUFFICIENT_CREDITS') {
    return 'More credits every month';
  }
  if (detail.feature && detail.feature in FEATURE_LABELS) {
    return FEATURE_LABELS[detail.feature as PlanFeature];
  }
  return 'This feature';
}

/**
 * The signed-in user's plan in the terms the UI needs: whether they are Pro,
 * whether a feature is included, and how much of a daily limit is left.
 * Everything is derived from the server's entitlements, which the API enforces
 * on its own, so a locked control here is for clarity rather than security.
 */
export function usePlan() {
  const { entitlements, isLoading, promptUpgrade, refresh } = useEntitlements();

  return useMemo(() => {
    const expiresInDays = daysUntil(entitlements.plan_expires_at);
    return {
      plan: entitlements.plan,
      isPro: isPaidPlan(entitlements),
      isLoading,
      canUse: (feature: PlanFeature) => canUseFeature(entitlements, feature),
      /** Uses left today, or null when the plan has no limit. */
      remainingToday: (key: UsageKey): number | null => {
        const limit = entitlements.daily_limits[key];
        return limit === null ? null : Math.max(0, limit - (entitlements.usage_today[key] ?? 0));
      },
      expiresAt: entitlements.plan_expires_at,
      expiresInDays,
      isExpiringSoon: isPaidPlan(entitlements) && expiresInDays !== null && expiresInDays <= RENEWAL_REMINDER_DAYS,
      hasPendingPayment: entitlements.has_pending_payment,
      showPlanNotice: entitlements.show_plan_notice,
      promptUpgrade,
      refresh,
    };
  }, [entitlements, isLoading, promptUpgrade, refresh]);
}
