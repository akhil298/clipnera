'use client';

import { useRouter } from 'next/navigation';

import { useMe } from '@/components/shell';

import { WelcomeDialog } from './WelcomeDialog';

/** `/dashboard/welcome` as a modal: Back or any exit returns to the page underneath. */
export function WelcomeRoute() {
  const router = useRouter();
  const me = useMe();
  if (!me.data) return null;
  return <WelcomeDialog open onClose={() => router.back()} userId={me.data.id} creditMinutes={me.data.ai_credits_minutes_remaining} />;
}
