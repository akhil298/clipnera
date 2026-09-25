'use client';

import { useEffect, useState } from 'react';
import { hookTransitionApi } from '@/lib/api';
import type { HookTransitionCatalog } from '@/lib/types';

// The catalog is static server data, so one fetch serves every editor mount.
let cached: HookTransitionCatalog | null = null;
let inflight: Promise<HookTransitionCatalog> | null = null;

const loadCatalog = (): Promise<HookTransitionCatalog> => {
  if (cached) return Promise.resolve(cached);
  inflight ??= hookTransitionApi.getCatalog().then(
    (catalog) => {
      cached = catalog;
      return catalog;
    },
    (error) => {
      // Let a later mount retry instead of caching the failure.
      inflight = null;
      throw error;
    },
  );
  return inflight;
};

export function useHookTransitionCatalog() {
  const [catalog, setCatalog] = useState<HookTransitionCatalog | null>(cached);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cached) return;
    let active = true;
    loadCatalog()
      .then((result) => active && setCatalog(result))
      .catch((err: Error) => active && setError(err.message || 'Could not load hook transitions'));
    return () => {
      active = false;
    };
  }, []);

  return { catalog, error };
}
