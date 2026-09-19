'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { subscriptionApi, type EntitlementsResponse } from '@/lib/api';
import {
  EntitlementsContext,
  FREE_TIER_FALLBACK,
} from '@/hooks/useEntitlements';

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
