'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  subscriptionApi,
  UPGRADE_REQUIRED_EVENT,
  type EntitlementsResponse,
  type UpgradeRequiredDetail,
} from '@/lib/api';
import { upgradeReasonFor } from '@/hooks/usePlan';
import {
  EntitlementsContext,
  FREE_TIER_FALLBACK,
} from '@/hooks/useEntitlements';

const PENDING_PAYMENT_POLL_MS = 30_000;

interface EntitlementsProviderProps {
  children: React.ReactNode;
  /** Whether the user is signed in. Entitlements are only fetched when they are. */
  isAuthed: boolean;
  /** Opens the plan/upgrade modal. */
  onPromptUpgrade: (reason?: string) => void;
  /** Bump to refetch after a plan change (e.g. payment completed). */
  refreshKey?: number;
}

export function EntitlementsProvider({
  children,
  isAuthed,
  onPromptUpgrade,
  refreshKey = 0,
}: EntitlementsProviderProps) {
  const [entitlements, setEntitlements] =
    useState<EntitlementsResponse>(FREE_TIER_FALLBACK);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    if (!isAuthed) {
      setEntitlements(FREE_TIER_FALLBACK);
      setIsLoading(false);
      return;
    }
    try {
      const next = await subscriptionApi.getEntitlements();
      setEntitlements(next);
    } catch {
      // Stay on the free-tier fallback. The server enforces the same rules, so
      // a failed read degrades to "locked" rather than handing out paid features.
      setEntitlements(FREE_TIER_FALLBACK);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthed]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await load();
      if (cancelled) return;
    })();
    return () => {
      cancelled = true;
    };
  }, [load, refreshKey]);

  // A plan can change outside this tab: an admin approving a UPI payment, or a
  // purchase in another tab. Refetch when the tab comes back into view, and
  // poll while a payment awaits approval, so the upgrade shows without a reload.
  useEffect(() => {
    if (!isAuthed) return;
    const onVisible = () => {
      if (document.visibilityState === 'visible') void load();
    };
    document.addEventListener('visibilitychange', onVisible);
    const poll = entitlements.has_pending_payment
      ? window.setInterval(() => void load(), PENDING_PAYMENT_POLL_MS)
      : undefined;
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.clearInterval(poll);
    };
  }, [isAuthed, load, entitlements.has_pending_payment]);

  // Any request refused for the plan opens the upsell, wherever it was made,
  // and refetches so limits and lock states catch up with the server.
  useEffect(() => {
    const onUpgradeRequired = (event: Event) => {
      onPromptUpgrade(upgradeReasonFor((event as CustomEvent<UpgradeRequiredDetail>).detail));
      void load();
    };
    window.addEventListener(UPGRADE_REQUIRED_EVENT, onUpgradeRequired);
    return () => window.removeEventListener(UPGRADE_REQUIRED_EVENT, onUpgradeRequired);
  }, [onPromptUpgrade, load]);

  const value = useMemo(
    () => ({
      entitlements,
      isLoading,
      promptUpgrade: onPromptUpgrade,
      refresh: load,
    }),
    [entitlements, isLoading, onPromptUpgrade, load],
  );

  return (
    <EntitlementsContext.Provider value={value}>
      {children}
    </EntitlementsContext.Provider>
  );
}
