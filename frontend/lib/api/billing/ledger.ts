'use client';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api/client';
import { billingKeys } from '@/lib/query/keys/billing';

import type { CreditLedgerEntry } from './types';

/** Rows the billing page's Credit history shows. */
export const LEDGER_PAGE = 30;

/**
 * `GET /subscription/ledger?limit=` (list[CreditLedgerResponse], bare body), newest first.
 * The backend reads `limit` (default 50) but does not cap it yet (L-API-12).
 */
export const listLedger = (limit: number, signal?: AbortSignal) =>
  apiFetch<CreditLedgerEntry[]>('/subscription/ledger', { query: { limit }, signal });

/** Credit history; loads only once the disclosure opens (`enabled`). */
export function useLedger(enabled: boolean, limit = LEDGER_PAGE) {
  return useQuery({ queryKey: billingKeys.ledger(limit), queryFn: ({ signal }) => listLedger(limit, signal), enabled, staleTime: 60_000 });
}
