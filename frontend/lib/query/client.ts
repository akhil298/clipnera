import { QueryClient, isServer } from '@tanstack/react-query';

import { isApiError, isRetryable } from '@/lib/api/errors';

const MAX_RETRIES = 2;
const MAX_RETRY_DELAY_MS = 10_000;

/** Defaults from docs/revamp/architecture/frontend.md §3.4. Override per query, never here. */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: (failures, err) => failures < MAX_RETRIES && isRetryable(err),
        // Exponential with jitter, capped; a 429 waits for its Retry-After.
        retryDelay: (attempt, err) => {
          if (isApiError(err) && err.retryAfter) return Math.min(err.retryAfter * 1000, MAX_RETRY_DELAY_MS);
          return Math.min(2 ** attempt * 500 + Math.random() * 250, MAX_RETRY_DELAY_MS);
        },
      },
      mutations: { retry: false },
    },
  });
}

let browserClient: QueryClient | undefined;

/** One client per browser tab; a fresh one per server render so users never share a cache. */
export function getQueryClient(): QueryClient {
  if (isServer) return makeQueryClient();
  browserClient ??= makeQueryClient();
  return browserClient;
}
