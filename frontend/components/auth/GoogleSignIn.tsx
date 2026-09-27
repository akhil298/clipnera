'use client';

import { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { startGoogleSignIn } from '@/lib/googleAuth';

interface GoogleSignInProps {
  mode?: 'login' | 'register';
}

function GoogleLogo() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z" />
    </svg>
  );
}

export function GoogleSignIn({ mode = 'login' }: GoogleSignInProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acceptTerms, setAcceptTerms] = useState(false);

  const handleClick = () => {
    setError(null);
    setLoading(true);
    try {
      startGoogleSignIn(acceptTerms);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not start Google sign-in.');
      setLoading(false);
    }
  };

  return (
    <div className="w-full rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 shadow-xl">
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold mb-1.5 font-['Syne',sans-serif] text-white">
          {mode === 'login' ? 'Welcome back' : 'Create account'}
        </h2>
        <p className="text-neutral-400 text-xs">
          {mode === 'login' ? 'Sign in to continue to Clipnera' : 'Start creating viral clips with AI'}
        </p>
      </div>

      <label className="mb-4 flex items-start gap-2.5 text-[11px] text-neutral-300 leading-relaxed cursor-pointer">
        <input
          type="checkbox"
          checked={acceptTerms}
          onChange={(e) => setAcceptTerms(e.target.checked)}
          className="mt-0.5 w-4 h-4 shrink-0 accent-amber-500"
        />
        <span>
          I am 18 or older and I agree to the{' '}
          <a href="/terms" target="_blank" className="text-amber-300 underline underline-offset-2">Terms of Service</a> and{' '}
          <a href="/privacy" target="_blank" className="text-amber-300 underline underline-offset-2">Privacy Policy</a>.
        </span>
      </label>

      <button
        type="button"
        onClick={handleClick}
        disabled={loading || !acceptTerms}
        className="w-full py-2.5 rounded-xl bg-white hover:bg-neutral-100 text-neutral-900 font-bold transition-all active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2.5 text-xs shadow-md"
      >
        {loading ? (
          <div className="w-4 h-4 border-2 border-neutral-900/30 border-t-neutral-900 rounded-full animate-spin" />
        ) : (
          <>
            <GoogleLogo />
            Continue with Google
          </>
        )}
      </button>

      {error && (
        <div role="alert" className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2">
          <AlertCircle size={14} aria-hidden="true" />
          {error}
        </div>
      )}
    </div>
  );
}
