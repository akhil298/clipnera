'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { socialApi, type SocialPlatform } from '@/lib/api';
import { PLATFORM_STYLE, SOCIAL_SETTINGS_PATH } from '@/components/social/platforms';

const PLATFORMS: SocialPlatform[] = ['youtube', 'tiktok', 'instagram', 'x'];

/**
 * OAuth redirect target: https://<app>/dashboard/connect/<platform>?code&state.
 *
 * The code and state are read once, stripped from the address bar and history
 * immediately, then sent to the backend with the user's session, which checks
 * the state belongs to this user and exchanges the code server-side. The route
 * is served with Referrer-Policy: no-referrer (next.config.mjs).
 */
export default function ConnectCallbackPage() {
  const params = useParams<{ platform: string }>();
  const router = useRouter();
  const handled = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const platform = PLATFORMS.find((p) => p === params.platform);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;
    const query = new URLSearchParams(window.location.search);
    window.history.replaceState(null, '', window.location.pathname);

    const denied = query.get('error_description') || query.get('error');
    const code = query.get('code');
    const state = query.get('state');
    if (!platform || denied || !code || !state) {
      setError(denied ? 'The connection was cancelled.' : 'This connection link is invalid.');
      return;
    }
    socialApi
      .completeConnect(platform, { code, state })
      .then(() => router.replace(SOCIAL_SETTINGS_PATH))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not connect the account.'));
  }, [platform, router]);

  return (
    <div className="min-h-screen bg-neutral-950 flex items-center justify-center p-6">
      <div className="max-w-sm w-full p-6 rounded-2xl bg-neutral-900 border border-neutral-800 text-center space-y-3">
        {error ? (
          <>
            <h1 className="text-sm font-bold text-white">
              Could not connect {platform ? PLATFORM_STYLE[platform].name : 'the account'}
            </h1>
            <p className="text-xs text-neutral-400">{error}</p>
            <button
              onClick={() => router.replace(SOCIAL_SETTINGS_PATH)}
              className="px-4 py-2 rounded-lg text-xs font-bold bg-amber-500 hover:bg-amber-400 text-neutral-950"
            >
              Back to settings
            </button>
          </>
        ) : (
          <div className="flex items-center justify-center gap-2 text-xs text-neutral-300">
            <Loader2 className="w-4 h-4 animate-spin" />
            Connecting {platform ? PLATFORM_STYLE[platform].name : 'your account'}…
          </div>
        )}
      </div>
    </div>
  );
}
