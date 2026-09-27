'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { authApi } from '@/lib/api';
import { consumeGoogleAcceptTerms, consumeGoogleState, googleRedirectUri } from '@/lib/googleAuth';

/**
 * Google sign-in redirect target: https://<app>/login/google?code&state.
 *
 * The code and state are read once and stripped from the address bar, the state
 * is checked against the one this tab sent, and the code is exchanged by the
 * backend for a Clipnera session. Served with Referrer-Policy: no-referrer
 * (next.config.mjs).
 */
export default function GoogleCallbackPage() {
  const router = useRouter();
  const handled = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;
    const query = new URLSearchParams(window.location.search);
    window.history.replaceState(null, '', window.location.pathname);

    const denied = query.get('error');
    const code = query.get('code');
    const state = query.get('state');
    if (denied || !code || !state) {
      setError(denied ? 'Google sign-in was cancelled.' : 'This sign-in link is invalid.');
      return;
    }
    if (!consumeGoogleState(state)) {
      setError('This sign-in link has expired. Please try again.');
      return;
    }
    authApi
      .oauthLogin('google', { code, redirect_uri: googleRedirectUri(), accept_terms: consumeGoogleAcceptTerms() })
      .then(() => router.replace('/dashboard'))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not sign in with Google.'));
  }, [router]);

  return (
    <div className="min-h-screen bg-neutral-950 flex items-center justify-center p-6 font-['Plus_Jakarta_Sans',sans-serif]">
      <div className="max-w-sm w-full p-6 rounded-2xl bg-neutral-900 border border-neutral-800 text-center space-y-3">
        {error ? (
          <>
            <h1 className="text-sm font-bold text-white">Could not sign you in</h1>
            <p className="text-xs text-neutral-400">{error}</p>
            <button
              onClick={() => router.replace('/login')}
              className="px-4 py-2 rounded-lg text-xs font-bold bg-amber-500 hover:bg-amber-400 text-neutral-950"
            >
              Back to sign in
            </button>
          </>
        ) : (
          <div className="flex items-center justify-center gap-2 text-xs text-neutral-300">
            <Loader2 className="w-4 h-4 animate-spin" />
            Signing you in with Google…
          </div>
        )}
      </div>
    </div>
  );
}
