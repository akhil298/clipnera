'use client';

import { useQuery } from '@tanstack/react-query';

import { getEntitlements, getPendingPayment, listCreditPacks } from '@/lib/api/credits';
import { creditKeys } from '@/lib/query/keys/credits';

const MINUTE = 60_000;
/** While an admin is checking a UPI payment, look for the approval this often. */
const PENDING_POLL_MS = 30_000;

/**
 * Balance and billing state for the credits popover. Packs and the pending
 * payment load only once the popover asks for them (`detail`).
 */
export function useCredits(detail: boolean) {
  const entitlements = useQuery({
    queryKey: creditKeys.entitlements(),
    queryFn: ({ signal }) => getEntitlements(signal),
    staleTime: MINUTE,
    refetchInterval: (query) => (query.state.data?.has_pending_payment ? PENDING_POLL_MS : false),
  });
  const pendingExpected = entitlements.data?.has_pending_payment ?? false;

  const packs = useQuery({
    queryKey: creditKeys.packs(),
    queryFn: ({ signal }) => listCreditPacks(signal),
    enabled: detail,
    staleTime: 30 * MINUTE,
  });

  const pending = useQuery({
    queryKey: creditKeys.payments(),
    queryFn: ({ signal }) => getPendingPayment(signal),
    enabled: detail && pendingExpected,
    staleTime: PENDING_POLL_MS,
  });

  return { entitlements, packs, pending: pendingExpected ? pending.data ?? null : null };
}
