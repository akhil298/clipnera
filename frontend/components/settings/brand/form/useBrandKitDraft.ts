'use client';

import { useCallback, useState } from 'react';

import { toRequest } from '@/lib/api/brand/kit';
import type { BrandKit, CreateBrandKitRequest } from '@/lib/api/brand/types';

export type UpdateKit = (changes: Partial<CreateBrandKitRequest>) => void;

const snapshot = (kit: CreateBrandKitRequest) => JSON.stringify(toRequest(kit));

/**
 * The edits on top of the saved kit. `reset` puts the form back to a kit (after
 * Discard or a save) and bumps `resetKey`, so uncontrolled bits (the colour
 * pickers' hex fields) remount to match.
 */
export function useBrandKitDraft(saved: BrandKit) {
  const [draft, setDraft] = useState<CreateBrandKitRequest>(() => toRequest(saved));
  const [resetKey, setResetKey] = useState(0);

  const update = useCallback<UpdateKit>((changes) => setDraft((kit) => ({ ...kit, ...changes })), []);
  const reset = useCallback((kit: BrandKit) => {
    setDraft(toRequest(kit));
    setResetKey((key) => key + 1);
  }, []);

  return { draft, update, reset, resetKey, dirty: snapshot(draft) !== snapshot(saved) };
}
