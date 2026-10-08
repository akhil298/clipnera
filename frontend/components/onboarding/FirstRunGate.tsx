'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { hasPendingPrompt, markSignedIn, takeSignInNext } from '@/components/auth-v2/session';
import { useMe } from '@/components/shell';
import { HOME_PATH } from '@/lib/routing/auth-rules';

import { WelcomeDialog } from './WelcomeDialog';

/**
 * Runs once per signed-in page load, on Home:
 * 1. remembers that this device has signed in (hides the consent box next time);
 * 2. finishes `?next=` from sign-in, since the Google callback always lands on /dashboard;
 * 3. opens the welcome while `/me` says the one-time form isn't filled in and the person
 *    arrived with nothing to do. A carried prompt wins: Home restores it and the welcome
 *    waits for the next visit (screens/01 §4).
 *
 * `carriedIntent` is Home's own "I restored a prompt" flag. The gate also peeks
 * the draft itself, because its effect runs before Home's takes it.
 */
export function FirstRunGate({ carriedIntent = false }: { carriedIntent?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const me = useMe();
  const [decision, setDecision] = useState<'pending' | 'skip' | 'welcome'>('pending');
  const formPending = me.data?.onboarding_completed === false;

  useEffect(() => {
    markSignedIn();
    const next = takeSignInNext();
    if (next && next !== pathname) {
      setDecision('skip');
      router.replace(next);
    } else if (hasPendingPrompt()) {
      setDecision('skip');
    }
  }, [pathname, router]);

  useEffect(() => {
    if (!me.data || decision !== 'pending') return;
    setDecision(pathname === HOME_PATH && formPending ? 'welcome' : 'skip');
  }, [decision, pathname, me.data, formPending]);

  if (decision !== 'welcome' || carriedIntent || !me.data) return null;
  return (
    <WelcomeDialog
      open
      onClose={() => setDecision('skip')}
      formDone={!formPending}
      creditMinutes={me.data.ai_credits_minutes_remaining}
    />
  );
}
