'use client';

import React, { useState } from 'react';
import { AlertTriangle, Crown, X } from 'lucide-react';
import { userApi, type PlanFeature } from '@/lib/api';
import { useEntitlements } from '@/hooks/useEntitlements';
import { FEATURE_LABELS, usePlan } from '@/hooks/usePlan';

/** Features that moved from Free to Pro, listed in the one-time notice. */
const NEWLY_PRO_FEATURES: PlanFeature[] = [
  'all_hook_transitions',
  'brand_kit_edit',
  'team_members',
  'depth_captions',
  'batch_processing',
];

/** Plan messages shown above every dashboard view: the renewal reminder near
 * expiry and, once, the notice about features that moved to Pro. */
export function PlanBanner() {
  const { entitlements } = useEntitlements();
  const { isExpiringSoon, expiresInDays, showPlanNotice, promptUpgrade, refresh } = usePlan();
  const [dismissing, setDismissing] = useState(false);

  const dismissNotice = async () => {
    setDismissing(true);
    try {
      await userApi.dismissPlanNotice();
      await refresh();
    } finally {
      setDismissing(false);
    }
  };

  if (isExpiringSoon) {
    return (
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3">
        <span className="flex items-center gap-2 text-sm text-amber-200">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
          {expiresInDays === 0
            ? 'Your Pro plan expires today.'
            : `Your Pro plan expires in ${expiresInDays} day${expiresInDays === 1 ? '' : 's'}.`}
        </span>
        <button
          onClick={() => promptUpgrade()}
          className="rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-bold text-neutral-950 hover:bg-amber-400"
        >
          Renew
        </button>
      </div>
    );
  }

  if (!showPlanNotice) return null;

  const { exports, audio_enhancements } = entitlements.daily_limits;
  return (
    <div className="mb-4 rounded-xl border border-violet-400/30 bg-violet-500/10 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1.5">
          <p className="flex items-center gap-2 text-sm font-bold text-violet-200">
            <Crown className="h-4 w-4 text-violet-300" />
            Some features are now part of Pro
          </p>
          <p className="text-xs text-neutral-300">
            {NEWLY_PRO_FEATURES.map((feature) => FEATURE_LABELS[feature]).join(', ')} now need Pro.
            {exports !== null && audio_enhancements !== null &&
              ` Free includes ${exports} exports and ${audio_enhancements} audio enhancements a day.`}{' '}
            Your existing brand kits, team members and clips are kept.
          </p>
          <button onClick={() => promptUpgrade()} className="text-xs font-bold text-violet-300 hover:underline">
            See plans
          </button>
        </div>
        <button
          onClick={dismissNotice}
          disabled={dismissing}
          aria-label="Dismiss"
          className="rounded-lg p-1 text-neutral-400 hover:bg-neutral-800 hover:text-white disabled:opacity-50"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
