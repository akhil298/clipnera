'use client';

import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import { logout } from '@/lib/api/account';
import { clearAuth } from '@/lib/auth';

/**
 * Ends the server session, then always signs out locally: a failed logout call
 * must not leave someone signed in on a shared computer. The full page load
 * resets flags and every other per-user cache.
 */
export function useSignOut(): () => Promise<void> {
  const queryClient = useQueryClient();
  return useCallback(async () => {
    try {
      await logout();
    } catch {
      // The local sign-out below still happens; the server token expires on its own.
    }
    clearAuth();
    queryClient.clear();
    window.location.assign('/');
  }, [queryClient]);
}
