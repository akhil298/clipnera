import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { VersionStates } from './VersionStates';

export const metadata: Metadata = { title: 'Version history · Screens · Clipnera', robots: { index: false, follow: false } };

/** Version history mockup. Development only: production builds return 404. */
export default function VersionsPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <VersionStates />;
}
