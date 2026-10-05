import { useQuery } from '@tanstack/react-query';

import type { PlansResponse } from '@/lib/api';
import { apiFetch } from '@/lib/api/client';

/** `GET /subscription/plans` (backend/subscription/route.py, schema PlansResponse). Public: no sign-in needed. */
export function fetchPublicPlans(signal?: AbortSignal): Promise<PlansResponse> {
  return apiFetch<PlansResponse>('/subscription/plans', { auth: 'optional', signal });
}

export const marketingKeys = {
  plans: ['marketing', 'plans'] as const,
};

/** Plans change rarely; keep them for ten minutes. */
export function usePublicPlans() {
  return useQuery({
    queryKey: marketingKeys.plans,
    queryFn: ({ signal }) => fetchPublicPlans(signal),
    staleTime: 10 * 60_000,
  });
}

/** Percent saved by paying yearly instead of twelve months, from the server's own prices; null when there's no saving. */
export function yearlySaving(monthly: number, yearly: number): number | null {
  const full = monthly * 12;
  const saving = Math.round(((full - yearly) / full) * 100);
  return full > 0 && saving > 0 ? saving : null;
}
