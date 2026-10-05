'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { FlagsProvider } from '@/lib/flags/FlagsProvider';
import { getQueryClient } from '@/lib/query/client';

/** Client context for every page: server-state cache and flags. Renders no markup of its own. */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={getQueryClient()}>
      <FlagsProvider>{children}</FlagsProvider>
    </QueryClientProvider>
  );
}
