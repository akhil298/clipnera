import { Suspense } from 'react';

import { NewVideoDialog } from '@/components/upload/NewVideoDialog';

/** /dashboard/upload opened from inside the app: the dialog over the current page; Back closes it. */
export default function Page() {
  return (
    <Suspense>
      <NewVideoDialog />
    </Suspense>
  );
}
