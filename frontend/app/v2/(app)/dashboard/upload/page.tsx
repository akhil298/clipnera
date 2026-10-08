import type { Metadata } from 'next';
import { Suspense } from 'react';

import { NewVideoPage } from '@/components/upload/NewVideoPage';

export const metadata: Metadata = { title: 'New video' };

/** Direct load of /dashboard/upload. The form reads `?url=` / `?prompt=`, so it renders under Suspense. */
export default function Page() {
  return (
    <Suspense>
      <NewVideoPage />
    </Suspense>
  );
}
