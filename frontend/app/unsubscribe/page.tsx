'use client';

import { useEffect, useState } from 'react';
import { userApi } from '@/lib/api';
import { LegalPage } from '@/components/legal/LegalPage';

/**
 * Target of the unsubscribe link in account emails (?token=…). One click
 * confirms; it does not unsubscribe on load, so link scanners that open
 * emails' links cannot turn someone's emails off.
 */
export default function UnsubscribePage() {
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'working' | 'done'>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get('token');
    if (value) setToken(value);
    else setError('This unsubscribe link is incomplete.');
  }, []);

  const unsubscribe = async () => {
    if (!token) return;
    setStatus('working');
    setError(null);
    try {
      await userApi.unsubscribe({ token });
      setStatus('done');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not unsubscribe you.');
      setStatus('idle');
    }
  };

  return (
    <LegalPage title="Unsubscribe from Clipnera emails">
      {status === 'done' ? (
        <p role="status">
          Done. You will no longer receive account emails from Clipnera. You can turn them back on in Settings →
          Profile.
        </p>
      ) : (
        <>
          <p>
            Stop emails about failed posts and accounts that need reconnecting. Clipnera never sends marketing emails.
          </p>
          <button
            type="button"
            onClick={unsubscribe}
            disabled={!token || status === 'working'}
            className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold disabled:opacity-50"
          >
            {status === 'working' ? 'Unsubscribing…' : 'Unsubscribe'}
          </button>
        </>
      )}
      {error && (
        <p role="alert" className="text-rose-300">
          {error}
        </p>
      )}
    </LegalPage>
  );
}
