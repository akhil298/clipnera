import { Suspense } from 'react';

import { ClipneraLibrary } from '@/components/broll/library/browse/ClipneraLibrary';
import { BrowseSkeleton } from '@/components/broll/library/browse/BrowseSkeleton';

/** The Clipnera library (screens/03 §4). Data loads on the client: the token is not visible to the server yet. */
export default function LibraryPage() {
  return (
    <Suspense fallback={<BrowseSkeleton />}>
      <ClipneraLibrary />
    </Suspense>
  );
}
