import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { LibraryPanel } from '../_screens/LibraryPanel';

export const metadata: Metadata = { title: 'Editor library panel · Mockup · Clipnera', robots: { index: false, follow: false } };

/** Static mockup. Development only: production builds return 404. */
export default function Page() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <LibraryPanel />;
}
