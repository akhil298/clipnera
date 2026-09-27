'use client';

import React, { useEffect, useState } from 'react';
import { adminFeaturesApi, type AdminFeatureFlagResponse, type FeatureFlagKey } from '@/lib/api';

/** On/off switches for the admin-controlled flags that ``show`` selects. */
export function FeatureSwitches({ show, onError }: { show: (key: FeatureFlagKey) => boolean; onError: (message: string) => void }) {
  const [flags, setFlags] = useState<AdminFeatureFlagResponse[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    adminFeaturesApi.list().then((res) => setFlags(res.flags)).catch((err: Error) => onError(err.message));
  }, [onError]);

  const toggle = async (flag: AdminFeatureFlagResponse) => {
    setBusy(flag.key);
    try {
      setFlags((await adminFeaturesApi.set(flag.key, !flag.enabled)).flags);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setBusy(null);
    }
  };

  if (!flags) return <p className="text-xs text-neutral-400">Loading…</p>;
  return (
    <>
      {flags.filter((flag) => show(flag.key)).map((flag) => (
        <div key={flag.key} className={`flex items-center justify-between gap-4 ${flag.parent ? 'pl-6' : ''}`}>
          <div>
            <p className="text-xs font-bold text-white">{flag.label}</p>
            <p className="text-[11px] text-neutral-400">{flag.description}</p>
            {flag.enabled && !flag.effective && (
              <p className="text-[11px] text-amber-300">On, but inactive while the main switch is off.</p>
            )}
          </div>
          <button
            role="switch"
            aria-checked={flag.enabled}
            onClick={() => toggle(flag)}
            disabled={busy !== null}
            className={`relative w-11 h-6 rounded-full transition-colors shrink-0 disabled:opacity-50 ${
              flag.enabled ? 'bg-amber-500' : 'bg-neutral-700'
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                flag.enabled ? 'translate-x-5' : ''
              }`}
            />
          </button>
        </div>
      ))}
    </>
  );
}
