'use client';

import { useRouter } from 'next/navigation';

import { useMe } from '@/components/shell';
import { HOME_PATH } from '@/lib/routing/auth-rules';

import { WelcomeDialog } from './WelcomeDialog';

/**
 * `/dashboard/welcome`, opened on purpose (e.g. "Show the welcome again"). As an
 * intercepted modal, any exit goes back to the page underneath; loaded directly
 * (`fullPage`), it sits over Home and exits to Home.
 */
export function WelcomeRoute({ fullPage = false }: { fullPage?: boolean }) {
  const router = useRouter();
  const me = useMe();
  if (!me.data) return null;
  return (
    <WelcomeDialog
      open
      onClose={() => (fullPage ? router.replace(HOME_PATH) : router.back())}
      formDone={me.data.onboarding_completed}
      creditMinutes={me.data.ai_credits_minutes_remaining}
    />
  );
}
