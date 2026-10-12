'use client';

import React, { useEffect, useState } from 'react';
import { adminFeaturesApi, type AdminFeatureFlagResponse, type FeatureFlagKey } from '@/lib/api';

/** On/off switches for the admin-controlled flags that ``show`` selects. */
export function FeatureSwitches({ show, onError }: { show: (key: FeatureFlagKey) => boolean; onError: (message: string) => void }) {
  const [flags, setFlags] = useState<AdminFeatureFlagResponse[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [emails, setEmails] = useState<Record<string, string>>({});

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

  const setTestUser = async (flag: AdminFeatureFlagResponse, email: string, allowed: boolean) => {
    if (!email.trim()) return;
    setBusy(flag.key);
    try {
      setFlags((await adminFeaturesApi.setTestUser(flag.key, email.trim(), allowed)).flags);
      if (allowed) setEmails((current) => ({ ...current, [flag.key]: '' }));
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
            {!flag.enabled && (
              <div className="mt-1.5 space-y-1">
                <p className="text-[11px] text-neutral-500">
                  Test users (on for them only){flag.test_users.length ? ':' : ': none'}
                </p>
                {flag.test_users.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {flag.test_users.map((email) => (
                      <span key={email} className="inline-flex items-center gap-1 rounded-md bg-neutral-800 px-1.5 py-0.5 text-[11px] text-neutral-200">
                        {email}
                        <button type="button" aria-label={`Remove ${email}`} disabled={busy !== null}
                          onClick={() => setTestUser(flag, email, false)} className="text-neutral-500 hover:text-rose-400">×</button>
                      </span>
                    ))}
                  </div>
                )}
                <form className="flex gap-1.5" onSubmit={(e) => { e.preventDefault(); void setTestUser(flag, emails[flag.key] ?? '', true); }}>
                  <input type="email" value={emails[flag.key] ?? ''} placeholder="name@example.com" aria-label={`Add a test user for ${flag.label}`}
                    onChange={(e) => setEmails((current) => ({ ...current, [flag.key]: e.target.value }))}
                    className="h-7 w-52 rounded-md border border-neutral-800 bg-neutral-950 px-2 text-[11px] text-white placeholder:text-neutral-600" />
                  <button type="submit" disabled={busy !== null} className="h-7 rounded-md border border-neutral-700 px-2 text-[11px] font-semibold text-amber-300 hover:border-amber-400 disabled:opacity-50">
                    Add
                  </button>
                </form>
              </div>
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
