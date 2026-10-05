import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { LibraryTrash } from '../_screens/LibraryCollections';

export const metadata: Metadata = { title: 'Recently deleted · Mockup · Clipnera', robots: { index: false, follow: false } };

/** Static mockup. Development only: production builds return 404. */
export default function Page() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <LibraryTrash />;
}
