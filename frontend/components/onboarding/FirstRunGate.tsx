'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { hasPendingPrompt, markSignedIn, takeSignInNext } from '@/components/auth-v2/session';
import { useMe } from '@/components/shell';
import { HOME_PATH } from '@/lib/routing/auth-rules';

import { readOnboarding } from './preferences';
import { WelcomeDialog } from './WelcomeDialog';

/**
 * Runs once per signed-in page load, on Home:
 * 1. remembers that this device has signed in (hides the consent box next time);
 * 2. finishes `?next=` from sign-in, since the Google callback always lands on /dashboard;
 * 3. opens the welcome when this account hasn't seen it and arrived with nothing to do.
 *    A carried prompt wins: Home restores it and the welcome waits (screens/01 §4).
 *
 * `carriedIntent` is Home's own "I restored a prompt" flag. The gate also peeks
 * the draft itself, because its effect runs before Home's takes it.
 */
export function FirstRunGate({ carriedIntent = false }: { carriedIntent?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const me = useMe();
  const [decision, setDecision] = useState<'pending' | 'skip' | 'welcome'>('pending');
  const userId = me.data?.id;

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
    if (!userId || decision !== 'pending') return;
    setDecision(pathname === HOME_PATH && !readOnboarding(userId) ? 'welcome' : 'skip');
  }, [decision, pathname, userId]);

  if (decision !== 'welcome' || carriedIntent || !userId) return null;
  return (
    <WelcomeDialog
      open
      onClose={() => setDecision('skip')}
      userId={userId}
      creditMinutes={me.data?.ai_credits_minutes_remaining ?? null}
    />
  );
}
