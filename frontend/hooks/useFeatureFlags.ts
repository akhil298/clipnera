'use client';

import { useCallback, useEffect, useState } from 'react';
import { featuresApi, type FeatureFlagKey } from '@/lib/api';

/** Everything off: used until the flags load and if the request fails, so a
 * dark-launched feature never flashes into view. */
const ALL_OFF: Record<FeatureFlagKey, boolean> = {
  social_publishing: false,
  'social_publishing.youtube': false,
  'social_publishing.tiktok': false,
  'social_publishing.instagram': false,
  'social_publishing.x': false,
  video_upload: false,
  broll_studio: false,
  'broll_studio.cutaways': false,
  'broll_studio.reels': false,
  'broll_studio.ai_shots': false,
};

// One request per page load, shared by every component that asks.
let cached: Promise<Record<FeatureFlagKey, boolean>> | null = null;

function load(force = false): Promise<Record<FeatureFlagKey, boolean>> {
  if (!cached || force) {
    cached = featuresApi
      .get()
      .then((res) => ({ ...ALL_OFF, ...res.flags }))
      .catch(() => {
        cached = null;
        return ALL_OFF;
      });
  }
  return cached;
}

/** Admin-controlled feature switches (backend feature_flags/). The API enforces
 * them too; this only decides what the UI shows. */
export function useFeatureFlags() {
  const [flags, setFlags] = useState<Record<FeatureFlagKey, boolean> | null>(null);

  useEffect(() => {
    let active = true;
    void load().then((loaded) => active && setFlags(loaded));
    return () => {
      active = false;
    };
  }, []);

  const refresh = useCallback(async () => setFlags(await load(true)), []);

  return { flags: flags ?? ALL_OFF, isLoading: flags === null, refresh };
}
