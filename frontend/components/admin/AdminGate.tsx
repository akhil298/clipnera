'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { userApi } from '@/lib/api';
import { getToken } from '@/lib/auth';

/** Redirects anyone who is not an admin. The API enforces this independently. */
function useAdminGate(): boolean {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    userApi
      .getMe()
      .then((profile) => {
        if (profile.role === 'admin') setAllowed(true);
        else router.replace('/dashboard');
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  return allowed;
}

/** Renders admin pages only once the caller is confirmed as an admin, so no
 * admin request fires for anyone else. The API enforces this independently. */
export function AdminGate({ children }: { children: React.ReactNode }) {
  if (!useAdminGate()) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-950">
        <div className="w-6 h-6 border-2 border-neutral-700 border-t-amber-400 rounded-full animate-spin" />
      </div>
    );
  }
  return <>{children}</>;
}
