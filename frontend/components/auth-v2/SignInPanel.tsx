'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { peekPendingPrompt, type PendingPrompt } from '@/components/home/handoff';
import { useOnline } from '@/components/home/useOnline';
import { Button, Checkbox, InlineAlert } from '@/components/ui';
import { getToken } from '@/lib/auth';
import { cx, focusRing } from '@/lib/design/styles';
import { startGoogleSignIn } from '@/lib/googleAuth';
import { HOME_PATH, safeNextPath } from '@/lib/routing/auth-rules';

import { GoogleMark } from './GoogleMark';
import { KeptPromptNote } from './KeptPromptNote';
import {
  consentWasSkipped,
  hasSignedInBefore,
  rememberSignInNext,
  setConsentSkipped,
} from './session';

const LINK = cx('rounded-cn-xs text-cn-accent-text underline underline-offset-2', focusRing);

interface DeviceState {
  /** Signed in here before, and no unticked attempt is waiting: the box is hidden. */
  returning: boolean;
  /** The last attempt went to Google without the tick and didn't come back signed in. */
  consentRetry: boolean;
  prompt: PendingPrompt | null;
}

export interface SignInPanelProps {
  /** Raw `?next=`; validated here. */
  next?: string | null;
  /** `?reason=expired`. */
  expired?: boolean;
  /** Inside the landing page's Dialog, which supplies its own title. */
  inDialog?: boolean;
}

/**
 * The one sign-in surface (screens/01 §3, DS-10): the /login and /signup page
 * body, and the landing page's dialog body. It starts the same Google flow as
 * the legacy page (`lib/googleAuth.ts`), so `/login/google` stays the callback.
 * Consent is asked for, never forced: the backend needs it only when Google
 * creates the account (§3.1).
 */
export function SignInPanel({ next = null, expired = false, inDialog = false }: SignInPanelProps) {
  const router = useRouter();
  const online = useOnline();
  const [device, setDevice] = useState<DeviceState | null>(null);
  const [consent, setConsent] = useState(false);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const safeNext = safeNextPath(next);

  useEffect(() => {
    // Already signed in (audit 03 F5): straight on, nothing to ask.
    if (getToken()) {
      router.replace(safeNext ?? HOME_PATH);
      return;
    }
    const consentRetry = consentWasSkipped();
    setDevice({ returning: hasSignedInBefore() && !consentRetry, consentRetry, prompt: peekPendingPrompt() });
  }, [router, safeNext]);

  useEffect(() => {
    // Back from Google restores this page from the bfcache: never leave a dead "Opening Google".
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) setOpening(false);
    };
    window.addEventListener('pageshow', onPageShow);
    return () => window.removeEventListener('pageshow', onPageShow);
  }, []);

  const continueWithGoogle = () => {
    setError(null);
    setOpening(true);
    try {
      rememberSignInNext(safeNext);
      setConsentSkipped(!consent);
      startGoogleSignIn(consent);
    } catch (err) {
      const notConfigured = err instanceof Error && err.message.includes('not configured');
      setError(notConfigured ? 'Google sign-in isn’t set up on this server.' : 'I couldn’t open Google just now. Nothing was changed.');
      setOpening(false);
    }
  };

  const showConsent = device !== null && !device.returning;

  return (
    <div className="flex flex-col gap-5">
      {!inDialog && (
        <div className="space-y-1.5 text-center">
          <h1 className="text-cn-title-lg font-bold text-cn-fg">Sign in to Clipnera</h1>
          <p className="text-cn-body text-cn-fg-secondary">New here? Signing in with Google creates your account.</p>
        </div>
      )}

      {expired && (
        <InlineAlert tone="info" live="status">
          You were signed out after a while away. Sign in and I’ll take you back to the page you were on.
        </InlineAlert>
      )}
      {device?.prompt && <KeptPromptNote prompt={device.prompt} />}
      {device?.consentRetry && (
        <InlineAlert tone="warning" title="One more step if you’re new">
          Last time you continued without ticking the box. A new account needs it, so tick it and continue.
        </InlineAlert>
      )}

      {showConsent && (
        <div className="rounded-cn-md border border-cn-border p-3 text-left">
          <Checkbox
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            data-autofocus={device.consentRetry || undefined}
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
              </>
            }
            description="Needed once, when your account is created."
          />
        </div>
      )}

      <div className="flex flex-col gap-2">
        <Button
          size="lg"
          variant="secondary"
          fullWidth
          leadingIcon={<GoogleMark />}
          loading={opening}
          loadingLabel="Opening Google"
          disabled={!online}
          aria-describedby={online ? undefined : 'sign-in-offline'}
          onClick={continueWithGoogle}
        >
          Continue with Google
        </Button>
        {!online && (
          <p id="sign-in-offline" role="alert" className="text-center text-cn-caption text-cn-danger-text">
            You’re offline. Sign-in needs a connection; I’ll keep this page as it is.
          </p>
        )}
        {error && (
          <p role="alert" className="text-center text-cn-caption text-cn-danger-text">
            {error}
          </p>
        )}
      </div>

      {device?.returning && (
        <p className="text-center text-cn-caption text-cn-fg-muted">You’ve signed in on this device before, so there’s nothing to tick.</p>
      )}
      <p className="text-center text-cn-caption text-cn-fg-muted">Clipnera uses Google sign-in only. We never see your Google password.</p>
    </div>
  );
}
