'use client';

import { CircleAlert, ExternalLink, Sparkles, WifiOff } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusRing } from '@/lib/design/styles';

/** Google's four-colour "G" is a platform mark, the one place brand colours are allowed (02 §2.1). */
function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="size-4">
      <path fill="#4285F4" d="M22.6 12.2c0-.8-.1-1.4-.2-2.1H12v4h5.9c-.3 1.4-1 2.5-2.2 3.3v2.7h3.6c2.1-1.9 3.3-4.8 3.3-7.9z" />
      <path fill="#34A853" d="M12 23c3 0 5.5-1 7.3-2.7l-3.6-2.7c-1 .7-2.2 1.1-3.7 1.1-2.9 0-5.3-1.9-6.2-4.6H2.1v2.9C3.9 20.5 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.8 14.1c-.2-.7-.4-1.4-.4-2.1s.1-1.4.4-2.1V7H2.1C1.4 8.5 1 10.2 1 12s.4 3.5 1.1 5l3.7-2.9z" />
      <path fill="#EA4335" d="M12 5.4c1.6 0 3.1.6 4.2 1.7l3.2-3.2C17.5 2.1 15 1 12 1 7.7 1 3.9 3.5 2.1 7l3.7 2.9C6.7 7.2 9.1 5.4 12 5.4z" />
    </svg>
  );
}

const LINK = cx('rounded-cn-xs text-cn-accent-text underline underline-offset-2', focusRing);

export type SignInVariant = 'default' | 'carried' | 'returning' | 'expired' | 'redirecting' | 'offline';

/**
 * The one sign-in surface (DS-10 candidate): rendered by /login and /signup as a
 * page and by the landing page as a Dialog body. Consent shows until this
 * device has signed in once; it is required only when Google creates a new account.
 */
export function SignInPanel({ variant = 'default', inDialog = false }: { variant?: SignInVariant; inDialog?: boolean }) {
  const [consent, setConsent] = useState(false);
  const showConsent = variant !== 'returning';
  return (
    <div className="flex flex-col gap-5">
      {!inDialog && (
        <div className="space-y-1.5 text-center">
          <h1 className="text-cn-title-lg font-bold text-cn-fg">Sign in to Clipnera</h1>
          <p className="text-cn-body text-cn-fg-secondary">New here? Signing in with Google creates your account.</p>
        </div>
      )}

      {variant === 'carried' && (
        <div className="flex items-start gap-2.5 rounded-cn-md border border-cn-border bg-cn-surface p-3 text-left">
          <Sparkles aria-hidden className="mt-0.5 size-4 shrink-0 text-cn-accent-text" />
          <div className="min-w-0 space-y-0.5">
            <p className="text-cn-label font-semibold text-cn-fg">Your prompt and video are kept</p>
            <p className="truncate text-cn-caption text-cn-fg-muted">“Find the 5 best moments…” · youtube.com/watch?v=Qm3x…</p>
            <p className="text-cn-caption text-cn-fg-muted">They’ll be waiting on Home. Nothing runs until you press send.</p>
          </div>
        </div>
      )}
      {variant === 'expired' && (
        <div role="status" className="rounded-cn-md border border-cn-info/30 bg-cn-info-subtle p-3 text-left text-cn-label text-cn-info-text">
          You were signed out after a while away. Sign in and I’ll take you back to the page you were on.
        </div>
      )}
      {variant === 'offline' && (
        <div role="alert" className="flex items-center gap-2 rounded-cn-md border border-cn-danger/30 bg-cn-danger-subtle p-3 text-left text-cn-label text-cn-danger-text">
          <WifiOff aria-hidden className="size-4 shrink-0" />
          You’re offline. Sign-in needs a connection; I’ll keep this page as it is.
        </div>
      )}

      {showConsent && (
        <div className="rounded-cn-md border border-cn-border p-3 text-left">
          <Checkbox
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            label={
              <>
                I’m 18 or older and agree to the{' '}
                <a href="/terms" target="_blank" rel="noreferrer" className={LINK}>
                  Terms<span className="sr-only"> (opens in a new tab)</span>
                </a>{' '}
                and{' '}
                <a href="/privacy" target="_blank" rel="noreferrer" className={LINK}>
                  Privacy Policy<span className="sr-only"> (opens in a new tab)</span>
                </a>
                <ExternalLink aria-hidden className="ml-1 inline size-3 text-cn-fg-muted" />
              </>
            }
            description="Needed once, when your account is created."
          />
        </div>
      )}

      <Button
        size="lg"
        variant="secondary"
        fullWidth
        leadingIcon={<GoogleMark />}
        loading={variant === 'redirecting'}
        loadingLabel="Opening Google"
        disabled={variant === 'offline'}
      >
        Continue with Google
      </Button>
      {variant === 'returning' && (
        <p className="text-center text-cn-caption text-cn-fg-muted">You’ve signed in on this device before, so there’s nothing to tick.</p>
      )}
      <p className="text-center text-cn-caption text-cn-fg-muted">Clipnera uses Google sign-in only. We never see your Google password.</p>
    </div>
  );
}

/** The `/login/google` return card: working, consent needed, and the error variants. */
export function CallbackCard({ variant }: { variant: 'callback' | 'consent' | 'cancelled' | 'stale' }) {
  const [consent, setConsent] = useState(false);
  if (variant === 'callback') {
    return (
      <div role="status" className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-cn-title font-semibold">Signing you in</h1>
        <WorkingText className="text-cn-body">Checking with Google</WorkingText>
      </div>
    );
  }
  if (variant === 'consent') {
    return (
      <div className="flex flex-col gap-4 text-left">
        <div className="space-y-1">
          <h1 className="text-cn-title font-semibold">One more step</h1>
          <p className="text-cn-body text-cn-fg-secondary">This Google account is new to Clipnera. Confirm the line below and I’ll create your account.</p>
        </div>
        <div className="rounded-cn-md border border-cn-border p-3">
          <Checkbox
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            label={
              <>
                I’m 18 or older and agree to the <a href="/terms" className={LINK}>Terms</a> and <a href="/privacy" className={LINK}>Privacy Policy</a>
              </>
            }
          />
        </div>
        <Button size="lg" fullWidth disabled={!consent}>
          Create my account
        </Button>
        <Button variant="ghost" fullWidth>
          Use a different Google account
        </Button>
      </div>
    );
  }
  const copy =
    variant === 'cancelled'
      ? { title: 'Sign-in was cancelled', body: 'You closed the Google window before finishing. Nothing was created or changed.' }
      : { title: 'That sign-in took too long', body: 'It was started in another tab or more than 10 minutes ago. Start again; it takes a few seconds.' };
  return (
    <div role="alert" className="flex flex-col gap-4 text-left">
      <div className="flex items-start gap-3">
        <CircleAlert aria-hidden className="mt-1 size-5 shrink-0 text-cn-danger-text" />
        <div className="space-y-1">
          <h1 className="text-cn-title font-semibold">{copy.title}</h1>
          <p className="text-cn-body text-cn-fg-secondary">{copy.body}</p>
        </div>
      </div>
      <Button size="lg" fullWidth>
        Try again
      </Button>
    </div>
  );
}
