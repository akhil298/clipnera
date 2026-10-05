'use client';

import { useQuery } from '@tanstack/react-query';
import { usePathname } from 'next/navigation';
import { createContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { apiFetch } from '@/lib/api/client';
import { flagKeys } from '@/lib/query/keys/flags';

import { CONFIG_DEFAULTS, FLAG_DEFAULTS, type ConfigValues, type FlagKey } from './registry.gen';
import { flagSubject, readSnapshot, writeSnapshot } from './snapshot';
import type { FlagsBootstrapResponse } from './types';
import { UI_FLAGS_COOKIE, UI_FLAGS_TTL_SECONDS, encodeUiFlags } from './ui-areas';

export type FlagsSource = 'server' | 'snapshot' | 'defaults';

export interface FlagsState {
  flags: Record<FlagKey, boolean>;
  config: ConfigValues;
  version: number | null;
  source: FlagsSource;
  /** True once the server has answered for the current subject. */
  ready: boolean;
}

const DEFAULT_STATE: FlagsState = {
  flags: FLAG_DEFAULTS,
  config: CONFIG_DEFAULTS,
  version: null,
  source: 'defaults',
  ready: false,
};

export const FlagsContext = createContext<FlagsState>(DEFAULT_STATE);

const fetchBootstrap = (signal: AbortSignal) =>
  apiFetch<FlagsBootstrapResponse>('/flags/bootstrap', { auth: 'optional', signal });

/** Lets middleware route a signed-in user's next navigation by their own flags (the API token is not a cookie yet). */
function rememberUiFlags(payload: FlagsBootstrapResponse): void {
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `${UI_FLAGS_COOKIE}=${encodeUiFlags(payload.flags)}; Path=/; Max-Age=${UI_FLAGS_TTL_SECONDS}; SameSite=Lax${secure}`;
}

/**
 * One copy of the caller's flags for the whole tree. Server render and first client render use the
 * generated defaults (so hydration matches); then the last snapshot for this user shows at once and
 * the bootstrap replaces it. Refetches on tab focus and every `poll_seconds`.
 */
export function FlagsProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [subject, setSubject] = useState<string | null>(null);

  // Re-read on navigation: sign-in and sign-out change the token without remounting the root.
  useEffect(() => setSubject(flagSubject()), [pathname]);

  const query = useQuery<FlagsBootstrapResponse, Error, FlagsBootstrapResponse, ReturnType<typeof flagKeys.bootstrap>>({
    queryKey: flagKeys.bootstrap(subject ?? 'anonymous'),
    queryFn: ({ signal }) => fetchBootstrap(signal),
    enabled: subject !== null,
    staleTime: Infinity,
    refetchOnWindowFocus: 'always',
    refetchInterval: (q) => (q.state.data?.poll_seconds ?? CONFIG_DEFAULTS['flags.client_poll_seconds']) * 1000,
    placeholderData: () => (subject ? readSnapshot(subject) : undefined),
  });

  const { data, isPlaceholderData } = query;
  useEffect(() => {
    if (!data || isPlaceholderData || !subject) return;
    writeSnapshot(subject, data);
    if (data.subject === 'user') rememberUiFlags(data);
  }, [data, isPlaceholderData, subject]);

  const state = useMemo<FlagsState>(() => {
    if (!data) return DEFAULT_STATE;
    return {
      flags: { ...FLAG_DEFAULTS, ...data.flags },
      config: { ...CONFIG_DEFAULTS, ...data.config } as ConfigValues,
      version: data.version,
      source: isPlaceholderData ? 'snapshot' : 'server',
      ready: !isPlaceholderData,
    };
  }, [data, isPlaceholderData]);

  return <FlagsContext.Provider value={state}>{children}</FlagsContext.Provider>;
}
