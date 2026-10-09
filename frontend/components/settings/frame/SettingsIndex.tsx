'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { Skeleton, SkeletonGroup } from '@/components/ui';

import { sectionById } from './sections';

const DESKTOP = '(min-width: 1024px)';

/**
 * `/dashboard/settings`. Phones and tablets see the section list (the frame draws it);
 * on a desktop, where the list is always beside the content, this opens Account.
 * Old links (`/dashboard/settings`, account emails) land here.
 */
export function SettingsIndex() {
  const router = useRouter();

  useEffect(() => {
    const query = window.matchMedia(DESKTOP);
    const open = () => {
      if (query.matches) router.replace(sectionById('account').href);
    };
    open();
    query.addEventListener('change', open);
    return () => query.removeEventListener('change', open);
  }, [router]);

  return (
    <SkeletonGroup label="Opening your account settings" className="space-y-6">
      <Skeleton className="h-40 w-full rounded-cn-lg" />
      <Skeleton className="h-56 w-full rounded-cn-lg" />
    </SkeletonGroup>
  );
}
