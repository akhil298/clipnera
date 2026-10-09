'use client';

import { RotateCcw } from 'lucide-react';

import { useMe } from '@/components/shell';
import { Button, InlineAlert, Skeleton, SkeletonGroup } from '@/components/ui';
import { accountMessage } from '@/lib/api/messages/account';

import { DeleteAccountCard } from './DeleteAccountCard';
import { LegalCard } from './LegalCard';
import { ProfileCard } from './ProfileCard';

/**
 * Settings → Account and privacy (screens/03 §9.2): profile, legal links, delete account.
 * Hidden until the backend exists: Privacy switch (L-API-7), sessions and "sign out
 * everywhere" (L-API-6), Member since and Age confirmed (L-API-5).
 * The legal card never depends on the profile, so it shows even when `/me` fails.
 */
export function AccountScreen() {
  const me = useMe();

  if (me.isPending) {
    return (
      <SkeletonGroup label="Loading your account" className="space-y-6">
        <Skeleton className="h-44 w-full rounded-cn-lg" />
        <Skeleton className="h-80 w-full rounded-cn-lg" />
        <Skeleton className="h-32 w-full rounded-cn-lg" />
      </SkeletonGroup>
    );
  }

  if (me.isError) {
    const message = accountMessage(me.error, 'load');
    return (
      <>
        <InlineAlert
          tone="danger"
          live="alert"
          title={message.title}
          action={
            <Button variant="secondary" size="sm" leadingIcon={<RotateCcw />} loading={me.isRefetching} loadingLabel="Trying again" onClick={() => void me.refetch()}>
              Try again
            </Button>
          }
        >
          {message.description}
        </InlineAlert>
        <LegalCard />
      </>
    );
  }

  return (
    <>
      <ProfileCard me={me.data} />
      <LegalCard />
      <DeleteAccountCard me={me.data} />
    </>
  );
}
